"""
barge_in.py — Interrupção por voz para o Burn (com cancelamento de eco acústico)

Ideia: enquanto o Burn está falando (TTS tocando), o microfone continua
gravando. Como o alto-falante e o microfone estão no mesmo ambiente, o
mic capta a própria fala do Burn (eco). Um filtro adaptativo NLMS usa o
áudio que está sendo reproduzido como "referência" e aprende a prever
e subtrair esse eco do sinal do microfone. O que sobra (o resíduo) é,
em teoria, só o que você está falando por cima. Um VAD simples de
energia decide se isso é "usuário falando" e, se for, interrompe a
reprodução na hora.

v2: além do NLMS + VAD por energia/pitch de antes, agora tem:

  1. Detector de double-talk (algoritmo de Geigel) — enquanto o mic capta
     um nível muito acima do que o Burn está tocando, o filtro NLMS
     praticamente para de se adaptar. Isso evita o problema mais comum de
     auto-interrupção: você fala por cima, o NLMS "surta" tentando
     aprender duas coisas ao mesmo tempo, os pesos saem do lugar, e sobra
     eco residual que dispara o VAD sozinho logo depois.

  2. Passo de adaptação (mu) e margem do VAD com MEMÓRIA entre sessões —
     salvos em barge_in_memory.json. A cada reprodução, o player registra
     se a interrupção "pareceu" falso positivo (aconteceu cedo demais,
     com pouca confiança de pitch) ou se tocou até o fim sem problema.
     Com base nisso, ajusta margem/mu aos poucos pras próximas
     reproduções — e persiste isso em disco, então o aprendizado
     continua na próxima vez que você rodar o Burn, não começa do zero.

Requisitos:
    pip install sounddevice numpy
"""

from __future__ import annotations

import collections
import json
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd


# --------------------------------------------------------------------------- #
# Estimativa do atraso (latência) entre a saída de áudio e a entrada do
# microfone. Alinhar isso ANTES do filtro adaptativo é essencial: o NLMS
# sozinho tenta aprender esse atraso junto com o cancelamento de eco, e
# isso é lento/instável logo no início de cada fala — é aí que sobra eco
# não cancelado e o VAD dispara por engano.
# --------------------------------------------------------------------------- #
def estimate_device_delay_samples(samplerate: int, margem_seguranca_ms: float = 30.0) -> int:
    """
    Estima o atraso típico de ida (saída) + volta (entrada) do dispositivo
    de áudio padrão, em amostras. Numa estimativa imprecisa (comum no
    Windows/MME), é melhor errar por excesso — por isso a margem de segurança.
    """
    try:
        info_saida = sd.query_devices(kind="output")
        info_entrada = sd.query_devices(kind="input")
        latencia_saida = info_saida.get("default_low_output_latency", 0.05)
        latencia_entrada = info_entrada.get("default_low_input_latency", 0.05)
        atraso_segundos = latencia_saida + latencia_entrada + (margem_seguranca_ms / 1000.0)
    except Exception:
        # se não conseguir consultar, assume um valor conservador
        atraso_segundos = 0.15

    return int(atraso_segundos * samplerate)


# --------------------------------------------------------------------------- #
# Memória persistente: o que o barge-in "aprendeu" entre sessões.
# --------------------------------------------------------------------------- #
DEFAULT_MEMORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "barge_in_memory.json"
)

_CAMPOS_PERSISTIDOS = (
    "noise_floor_ema",
    "vad_margin",
    "mu_base",
    "interrupcoes_precoces_seguidas",
    "reproducoes_completas_seguidas",
    "total_sessoes",
)


@dataclass
class BargeInMemory:
    """
    Guarda entre uma conversa e outra:
      - noise_floor_ema: o chão de ruído do ambiente já calibrado antes
      - vad_margin: quão acima do ruído de fundo precisa estar pra contar
        como "fala" (sobe se o sistema andou se auto-interrompendo demais,
        desce devagar se andou tocando sem problema, pra não ficar surdo)
      - mu_base: passo de adaptação do NLMS (baixa quando parece estar
        instável / gerando falsos positivos)
      - contadores usados só pra decidir quando ajustar os valores acima

    Sem isso, cada `python burn.py` começa recalibrando do zero e repete
    os mesmos erros da sessão anterior.
    """

    caminho: str = DEFAULT_MEMORY_PATH
    noise_floor_ema: float = None
    vad_margin: float = 6.0
    mu_base: float = 0.3
    interrupcoes_precoces_seguidas: int = 0
    reproducoes_completas_seguidas: int = 0
    total_sessoes: int = 0

    @classmethod
    def carregar(cls, caminho: str = DEFAULT_MEMORY_PATH) -> "BargeInMemory":
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                dados_validos = {k: v for k, v in dados.items() if k in _CAMPOS_PERSISTIDOS}
                return cls(caminho=caminho, **dados_validos)
            except Exception:
                pass  # arquivo corrompido/antigo — começa do padrão, sem quebrar
        return cls(caminho=caminho)

    def salvar(self):
        dados = {campo: getattr(self, campo) for campo in _CAMPOS_PERSISTIDOS}
        try:
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2)
        except OSError:
            pass  # não conseguir salvar não é crítico, só não persiste dessa vez


# --------------------------------------------------------------------------- #
# Detector de double-talk (algoritmo de Geigel)
# --------------------------------------------------------------------------- #
class GeigelDoubleTalkDetector:
    """
    Regra simples e clássica em AEC: se o microfone está captando um nível
    muito próximo (ou maior) do que o pico recente do que está sendo
    tocado, é muito provável que tenha ALGUÉM FALANDO além do eco — porque
    o eco puro, depois de atenuado pelo caminho acústico (distância,
    absorção do ambiente), normalmente chega mais fraco do que a fonte.

    Quando double-talk é suspeito, a adaptação do NLMS é bloqueada (ou
    bem reduzida) — ver `mu_scale` em NLMSEchoCanceller.process_block.
    Isso evita que os pesos do filtro sejam "estragados" pela sua voz
    real, o que é a causa mais comum de eco residual (e portanto
    auto-interrupção) logo depois que você fala.
    """

    def __init__(self, threshold_db: float = -6.0, janela_amostras: int = 4000):
        self.limiar_linear = 10 ** (threshold_db / 20.0)
        self._historico_ref_max = collections.deque(maxlen=janela_amostras // 256 + 1)

    def atualizar_referencia(self, ref_block: np.ndarray):
        pico = float(np.max(np.abs(ref_block))) if len(ref_block) else 0.0
        self._historico_ref_max.append(pico)

    def suspeita_double_talk(self, mic_block: np.ndarray) -> bool:
        if not self._historico_ref_max:
            return False
        pico_ref = max(self._historico_ref_max)
        if pico_ref < 1e-6:
            return False  # Burn em silêncio — qualquer coisa no mic não é double-talk, é só você
        pico_mic = float(np.max(np.abs(mic_block))) if len(mic_block) else 0.0
        return pico_mic > self.limiar_linear * pico_ref


# --------------------------------------------------------------------------- #
# Filtro adaptativo NLMS (Normalized Least Mean Squares)
# --------------------------------------------------------------------------- #
class NLMSEchoCanceller:
    """
    Aprende a mapear o áudio de referência (o que está saindo do alto-falante)
    para o eco que aparece no microfone, e subtrai essa estimativa do sinal
    captado. O que sobra é o resíduo (idealmente: a voz do usuário).
    """

    def __init__(self, filter_len: int = 512, mu: float = 0.5, eps: float = 1e-6):
        self.filter_len = filter_len
        self.mu = mu
        self.eps = eps
        self.weights = np.zeros(filter_len, dtype=np.float32)
        self.ref_history = np.zeros(filter_len, dtype=np.float32)

    def process_block(self, mic_block: np.ndarray, ref_block: np.ndarray, mu_scale: float = 1.0) -> np.ndarray:
        """
        Processa um bloco (mesmo tamanho) de mic e referência. Retorna o resíduo.

        mu_scale: reduz (ou zera) a adaptação nesse bloco — usado pelo
        detector de double-talk pra "congelar" o aprendizado quando há
        chance real de ser sua voz, e não eco, entrando no cálculo.
        """
        residual = np.empty_like(mic_block)
        passo_efetivo = self.mu * mu_scale
        for i, (d, x) in enumerate(zip(mic_block, ref_block)):
            # desloca o histórico de referência (janela deslizante)
            self.ref_history[1:] = self.ref_history[:-1]
            self.ref_history[0] = x

            # eco estimado = produto interno peso . histórico
            echo_estimate = np.dot(self.weights, self.ref_history)
            error = d - echo_estimate
            residual[i] = error

            if passo_efetivo > 0:
                # normalização pela energia da referência (é o "N" do NLMS)
                norm = np.dot(self.ref_history, self.ref_history) + self.eps
                self.weights += (passo_efetivo / norm) * error * self.ref_history

        return residual


# --------------------------------------------------------------------------- #
# Detector de pitch (frequência fundamental) por autocorrelação.
# Voz humana tem uma periodicidade clara nessa faixa; ruído de banda larga
# (eco residual não cancelado, ruído de fundo) geralmente não tem.
# --------------------------------------------------------------------------- #
def estimate_pitch(block: np.ndarray, samplerate: int, fmin: float = 80.0, fmax: float = 400.0):
    """
    Retorna (frequência_estimada, confiança) ou (None, 0.0) se não achar
    periodicidade clara na faixa de voz humana.
    """
    block = block.astype(np.float64) - np.mean(block)
    if np.max(np.abs(block)) < 1e-6:
        return None, 0.0

    corr = np.correlate(block, block, mode="full")
    corr = corr[len(corr) // 2 :]  # mantém só os lags >= 0

    if corr[0] <= 0:
        return None, 0.0

    min_lag = int(samplerate / fmax)
    max_lag = int(samplerate / fmin)
    max_lag = min(max_lag, len(corr) - 1)

    if min_lag >= max_lag:
        return None, 0.0

    segmento = corr[min_lag : max_lag + 1]
    if len(segmento) == 0:
        return None, 0.0

    pico_lag = int(np.argmax(segmento)) + min_lag
    confianca = corr[pico_lag] / corr[0]  # 1.0 = perfeitamente periódico

    if confianca < 0.35 or pico_lag == 0:
        return None, float(confianca)

    freq = samplerate / pico_lag
    return float(freq), float(confianca)


class PitchBuffer:
    """
    Mantém uma janela deslizante maior que um bloco só (pitch precisa de mais
    contexto que os ~16ms de um bloco de VAD pra ser estimado com confiança).
    """

    def __init__(self, samplerate: int, window_seconds: float = 0.05):
        self.samplerate = samplerate
        self.size = int(samplerate * window_seconds)
        self.buffer = np.zeros(self.size, dtype=np.float32)

    def push(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        if n >= self.size:
            self.buffer = block[-self.size :].copy()
        else:
            self.buffer[:-n] = self.buffer[n:]
            self.buffer[-n:] = block
        return self.buffer


# --------------------------------------------------------------------------- #
# VAD por energia, com calibração automática do ruído de fundo
# (resolve ruído constante tipo ventilador/ar-condicionado sem precisar
# de um denoiser separado: aprende o "chão de ruído" e só dispara bem
# acima dele)
# --------------------------------------------------------------------------- #
@dataclass
class EnergyVAD:
    calibration_blocks: int = 20   # quantos blocos iniciais usa pra medir o ruído de fundo
    margin: float = 6.0            # dispara quando a energia é `margin`x o ruído de fundo
    min_threshold: float = 0.005   # piso de segurança, mesmo em ambiente muito silencioso
    hold_blocks: int = 5           # nº de blocos consecutivos acima do limiar p/ confirmar fala
    noise_floor_alpha: float = 0.05  # taxa de adaptação do ruído de fundo (bem lenta, pra não "aprender" a fala como ruído)
    require_pitch: bool = True     # exige também periodicidade de voz humana, não só energia
    samplerate: int = 16000
    pitch_confianca_minima: float = 0.35
    tolerancia_pitch_hz: float = 25.0   # se o pitch do resíduo estiver a menos que isso do pitch da referência, considera "ainda é eco do Burn"
    limiar_referencia_silenciosa: float = 0.01  # abaixo disso, considera que o Burn está em silêncio/pausa
    initial_noise_floor: float = None  # semente vinda da memória entre sessões (opcional)

    def __post_init__(self):
        self._consecutive = 0
        self._calibrated_blocks = 0
        self._noise_floor = self.initial_noise_floor if self.initial_noise_floor else self.min_threshold
        self._pitch_buffer = PitchBuffer(self.samplerate) if self.require_pitch else None
        self._ref_pitch_buffer = PitchBuffer(self.samplerate) if self.require_pitch else None

    def _rms(self, block: np.ndarray) -> float:
        return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))

    def is_speech(self, block: np.ndarray, ref_block: np.ndarray = None) -> bool:
        rms = self._rms(block)

        # fase de calibração: primeiros blocos, assume silêncio/ruído de fundo
        # e usa pra estabelecer o chão de ruído inicial (partindo já do valor
        # aprendido em sessões anteriores, se houver — por isso converge mais
        # rápido e mais estável a cada vez que o Burn roda)
        if self._calibrated_blocks < self.calibration_blocks:
            self._noise_floor = max(
                self.min_threshold,
                (self._noise_floor * self._calibrated_blocks + rms) / (self._calibrated_blocks + 1),
            )
            self._calibrated_blocks += 1
            if self.require_pitch:
                self._pitch_buffer.push(block)
                if ref_block is not None:
                    self._ref_pitch_buffer.push(ref_block)
            return False

        threshold = max(self.min_threshold, self._noise_floor * self.margin)
        energia_ok = rms > threshold

        pitch_ok = True
        self.last_pitch = None
        self.last_pitch_confianca = 0.0
        self.last_ref_pitch = None
        self.last_motivo_bloqueio = None

        if self.require_pitch:
            janela = self._pitch_buffer.push(block)
            freq, confianca = estimate_pitch(janela, self.samplerate)
            self.last_pitch = freq
            self.last_pitch_confianca = confianca
            pitch_ok = freq is not None and confianca >= self.pitch_confianca_minima

            # cross-check com a referência: o Burn está falando algo com o
            # MESMO pitch que sobrou no resíduo? se sim, é eco, não é você.
            if pitch_ok and ref_block is not None:
                janela_ref = self._ref_pitch_buffer.push(ref_block)
                ref_rms = self._rms(ref_block)
                if ref_rms > self.limiar_referencia_silenciosa:
                    freq_ref, conf_ref = estimate_pitch(janela_ref, self.samplerate)
                    self.last_ref_pitch = freq_ref
                    if (
                        freq_ref is not None
                        and conf_ref >= self.pitch_confianca_minima
                        and abs(freq - freq_ref) <= self.tolerancia_pitch_hz
                    ):
                        pitch_ok = False
                        self.last_motivo_bloqueio = "pitch bate com o que o Burn está falando (eco)"
                # se o Burn está em silêncio/pausa (ref_rms baixo), não faz o
                # cross-check — qualquer voz real nesse instante não pode ser eco

        if energia_ok and pitch_ok:
            self._consecutive += 1
        else:
            self._consecutive = 0
            if not energia_ok:
                # segue adaptando devagar o chão de ruído quando está "quieto"
                self._noise_floor = (1 - self.noise_floor_alpha) * self._noise_floor + self.noise_floor_alpha * rms

        return self._consecutive >= self.hold_blocks

    def reset_calibration(self):
        """Chame isso no início de cada reprodução se o ambiente pode ter mudado."""
        self._calibrated_blocks = 0
        self._consecutive = 0


# --------------------------------------------------------------------------- #
# Utilitário: carrega um arquivo de áudio (mp3, wav, etc.) como array
# float32 mono, no samplerate desejado — usa pydub (precisa de ffmpeg
# instalado no sistema).
# --------------------------------------------------------------------------- #
def load_audio_as_float32(path: str, samplerate: int) -> np.ndarray:
    from pydub import AudioSegment

    seg = AudioSegment.from_file(path)
    seg = seg.set_channels(1).set_frame_rate(samplerate)
    samples = np.array(seg.get_array_of_samples()).astype(np.float32)
    samples /= float(1 << (8 * seg.sample_width - 1))  # normaliza pra faixa -1..1
    return samples


# --------------------------------------------------------------------------- #
# Player com barge-in
# --------------------------------------------------------------------------- #
class BargeInPlayer:
    """
    Toca um array de áudio (float32, mono) via sounddevice, cancelando o eco
    do microfone em tempo real. Se detectar fala do usuário, para a
    reprodução e chama on_interrupt().

    A cada reprodução, registra na `memory` se o resultado pareceu um falso
    positivo (interrompeu cedo demais / com pouca confiança) ou se tocou até
    o fim sem problema, e ajusta margem do VAD e passo do NLMS aos poucos —
    persistindo isso em disco pra próxima sessão continuar de onde parou.
    """

    def __init__(
        self,
        samplerate: int = 16000,
        block_size: int = 256,
        filter_len: int = 1024,
        vad_calibration_blocks: int = 20,
        vad_margin: float = None,
        vad_hold_blocks: int = 5,
        device_delay_ms: float = None,
        geigel_threshold_db: float = -6.0,
        memory: "BargeInMemory" = None,
        memory_path: str = DEFAULT_MEMORY_PATH,
        debug: bool = False,
    ):
        self.samplerate = samplerate
        self.block_size = block_size
        self.debug = debug

        # memória entre sessões: se não vier pronta, carrega do disco
        # (ou começa do zero, se essa for a primeira vez rodando o Burn)
        self.memory = memory if memory is not None else BargeInMemory.carregar(memory_path)

        # parâmetros explícitos passados na chamada sempre vencem os da
        # memória (assim dá pra forçar um valor específico se quiser testar
        # algo pontual sem mexer no que já foi aprendido)
        margem_inicial = vad_margin if vad_margin is not None else self.memory.vad_margin
        mu_inicial = self.memory.mu_base

        self.canceller = NLMSEchoCanceller(filter_len=filter_len, mu=mu_inicial)
        self.vad = EnergyVAD(
            calibration_blocks=vad_calibration_blocks,
            margin=margem_inicial,
            hold_blocks=vad_hold_blocks,
            samplerate=samplerate,
            initial_noise_floor=self.memory.noise_floor_ema,
        )
        self.dtd = GeigelDoubleTalkDetector(threshold_db=geigel_threshold_db)

        if device_delay_ms is not None:
            self.delay_samples = int(device_delay_ms / 1000.0 * samplerate)
        else:
            self.delay_samples = estimate_device_delay_samples(samplerate)

        self._warmup_samples = int(0.3 * samplerate)  # 300ms de carência pro filtro convergir

        if self.debug:
            print(f"[barge-in] atraso estimado do dispositivo: {self.delay_samples} amostras "
                  f"({self.delay_samples / samplerate * 1000:.0f} ms)")
            print(f"[barge-in] memória carregada: margem={margem_inicial:.2f}  mu={mu_inicial:.2f}  "
                  f"sessões anteriores={self.memory.total_sessoes}")

        self._interrupted = threading.Event()
        self._stop = threading.Event()

    # ----------------------------------------------------------------- #
    # Aprendizado entre sessões: decide se ajusta margem/mu com base em
    # como essa reprodução terminou, e persiste em disco.
    # ----------------------------------------------------------------- #
    def _registrar_interrupcao(self, posicao_amostras: int):
        tempo_desde_confirmacao = (
            posicao_amostras - self.delay_samples - self._warmup_samples
        ) / self.samplerate

        confianca_pitch = getattr(self.vad, "last_pitch_confianca", 0.0) or 0.0
        parece_falso_positivo = (
            tempo_desde_confirmacao < 0.5
            or confianca_pitch < (self.vad.pitch_confianca_minima + 0.1)
        )

        if parece_falso_positivo:
            self.memory.interrupcoes_precoces_seguidas += 1
            self.memory.reproducoes_completas_seguidas = 0
            # só reage depois de ver o padrão se repetir, pra não sair
            # ajustando por causa de um evento isolado
            if self.memory.interrupcoes_precoces_seguidas >= 2:
                self.memory.vad_margin = min(12.0, self.memory.vad_margin * 1.08)
                self.memory.mu_base = max(0.05, self.memory.mu_base * 0.85)
                self.memory.interrupcoes_precoces_seguidas = 0
                if self.debug:
                    print(
                        f"\n[barge-in] auto-interrupção recorrente detectada — "
                        f"subindo margem para {self.memory.vad_margin:.2f} e "
                        f"baixando mu para {self.memory.mu_base:.2f}"
                    )
        else:
            self.memory.interrupcoes_precoces_seguidas = 0
            self.memory.reproducoes_completas_seguidas = 0

    def _registrar_reproducao_completa(self):
        self.memory.interrupcoes_precoces_seguidas = 0
        self.memory.reproducoes_completas_seguidas += 1
        # se tocou várias vezes seguidas sem se interromper, relaxa um
        # pouco a margem de volta pra baixo — pra não ficar "surdo" demais
        if self.memory.reproducoes_completas_seguidas >= 5:
            self.memory.vad_margin = max(3.0, self.memory.vad_margin * 0.97)
            self.memory.reproducoes_completas_seguidas = 0

    def iniciar_calibracao(self):
        """
        Começa a gravar o trecho de calibração do microfone (ruído de fundo)
        numa thread separada, SEM bloquear quem chamou. Serve pra rodar essa
        gravação em paralelo com alguma outra coisa demorada — tipicamente a
        geração do áudio do TTS pela rede — em vez de só começar a calibrar
        DEPOIS que o áudio já está pronto. Passe o retorno pra `play(...,
        calibracao=...)`.
        """
        calib_duration = self.vad.calibration_blocks * self.block_size / self.samplerate
        n_amostras = int(calib_duration * self.samplerate)
        estado = {"audio": None}

        def _gravar():
            rec = sd.rec(n_amostras, samplerate=self.samplerate, channels=1, dtype="float32")
            sd.wait()
            estado["audio"] = rec[:, 0]

        thread = threading.Thread(target=_gravar, daemon=True)
        thread.start()
        return {"thread": thread, "estado": estado}

    def play(self, audio: np.ndarray, on_interrupt=None, calibracao=None) -> bool:
        """
        audio: array float32 mono, no mesmo samplerate configurado.
        on_interrupt: callback opcional, chamado assim que detecta fala.
        calibracao: opcional, retorno de `iniciar_calibracao()` chamado
        antes — se vier pronto, pula a espera de calibração aqui (ela já
        rodou em paralelo com outra coisa).
        Retorna True se foi interrompido, False se tocou até o fim.
        """
        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        self._interrupted.clear()
        self._stop.clear()
        self.vad.reset_calibration()

        # calibra o chão de ruído com ~300ms de silêncio ANTES de começar a
        # tocar (evita que o eco ainda não-convergido do início da reprodução
        # seja aprendido como "ruído normal"). Se já foi iniciada em paralelo
        # via iniciar_calibracao(), só espera ela terminar (geralmente já
        # terminou, porque o TTS demora mais que os 300ms de calibração).
        if calibracao is not None:
            calibracao["thread"].join()
            calib_audio = calibracao["estado"]["audio"]
        else:
            calib_duration = self.vad.calibration_blocks * self.block_size / self.samplerate
            calib_rec = sd.rec(
                int(calib_duration * self.samplerate),
                samplerate=self.samplerate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            calib_audio = calib_rec[:, 0]

        for i in range(0, len(calib_audio) - self.block_size + 1, self.block_size):
            self.vad.is_speech(calib_audio[i : i + self.block_size])

        n_blocks = int(np.ceil(len(audio) / self.block_size))
        padded_len = n_blocks * self.block_size
        if padded_len > len(audio):
            audio = np.pad(audio, (0, padded_len - len(audio)))

        play_pos = {"i": 0}
        interrupted_flag = {"v": False}

        def callback(indata, outdata, frames, time_info, status):
            i = play_pos["i"]
            ref_block_atual = audio[i : i + frames]
            outdata[:, 0] = ref_block_atual

            # referência alinhada: o áudio que está chegando AGORA no microfone
            # corresponde ao que foi tocado `delay_samples` atrás, não ao que
            # está sendo escrito neste exato callback
            i_alinhado = i - self.delay_samples
            if i_alinhado < 0:
                ref_block_alinhado = np.zeros(frames, dtype=np.float32)
                inicio_real = max(0, i_alinhado + frames)
                if inicio_real > 0:
                    ref_block_alinhado[-inicio_real:] = audio[0:inicio_real]
            else:
                ref_block_alinhado = audio[i_alinhado : i_alinhado + frames]
                if len(ref_block_alinhado) < frames:
                    ref_block_alinhado = np.pad(ref_block_alinhado, (0, frames - len(ref_block_alinhado)))

            mic_block = indata[:, 0]

            # double-talk: se o mic está captando algo forte demais pra ser
            # só o eco do que está sendo tocado, freia (quase) totalmente a
            # adaptação do NLMS nesse bloco, pra não corromper os pesos
            self.dtd.atualizar_referencia(ref_block_alinhado)
            double_talk_suspeito = self.dtd.suspeita_double_talk(mic_block)
            mu_scale = 0.05 if double_talk_suspeito else 1.0

            residual = self.canceller.process_block(mic_block, ref_block_alinhado, mu_scale=mu_scale)

            if self.debug:
                rms_residual = float(np.sqrt(np.mean(residual.astype(np.float64) ** 2)))
                threshold = max(self.vad.min_threshold, self.vad._noise_floor * self.vad.margin)
                pitch_info = ""
                if self.vad.require_pitch:
                    p = getattr(self.vad, "last_pitch", None)
                    c = getattr(self.vad, "last_pitch_confianca", 0.0)
                    p_ref = getattr(self.vad, "last_ref_pitch", None)
                    motivo = getattr(self.vad, "last_motivo_bloqueio", None)
                    pitch_info = (
                        f"  pitch_voc\u00ea={f'{p:.0f}Hz' if p else '---'}(conf={c:.2f})"
                        f"  pitch_burn={f'{p_ref:.0f}Hz' if p_ref else '---'}"
                    )
                    if motivo:
                        pitch_info += f"  [{motivo}]"
                dt_info = "  [double-talk]" if double_talk_suspeito else ""
                print(
                    f"[barge-in] resíduo={rms_residual:.4f}  "
                    f"chão_ruído={self.vad._noise_floor:.4f}  "
                    f"limiar={threshold:.4f}{pitch_info}{dt_info}",
                    end="\r",
                )

            # período de carência: logo no início, o filtro ainda não convergiu
            # de todo mesmo com o alinhamento grosseiro do atraso — não checa
            # interrupção até passar esse tempo
            em_carencia = i < (self.delay_samples + self._warmup_samples)

            if not em_carencia and self.vad.is_speech(residual, ref_block=ref_block_alinhado):
                interrupted_flag["v"] = True
                raise sd.CallbackStop()

            play_pos["i"] += frames
            if play_pos["i"] >= len(audio):
                raise sd.CallbackStop()

        with sd.Stream(
            samplerate=self.samplerate,
            blocksize=self.block_size,
            channels=1,
            dtype="float32",
            callback=callback,
        ):
            while play_pos["i"] < len(audio) and not interrupted_flag["v"]:
                time.sleep(0.01)

        # aprendizado entre sessões: atualiza e salva a memória
        self.memory.noise_floor_ema = self.vad._noise_floor
        self.memory.total_sessoes += 1
        if interrupted_flag["v"]:
            self._registrar_interrupcao(play_pos["i"])
        else:
            self._registrar_reproducao_completa()
        self.memory.salvar()

        if interrupted_flag["v"] and on_interrupt:
            on_interrupt()

        return interrupted_flag["v"]


# --------------------------------------------------------------------------- #
# Exemplo de uso isolado (rode `python barge_in.py` para testar)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print("Teste: gerando um tom de 2s e tentando tocar com barge-in.")
    print("Fale durante a reprodução para interromper.")

    sr = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = 0.2 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    player = BargeInPlayer(samplerate=sr, debug=True)
    stopped = player.play(tone, on_interrupt=lambda: print(">>> Interrompido pelo usuário!"))
    print("Terminou naturalmente." if not stopped else "Terminou por interrupção.")