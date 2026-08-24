import sounddevice as sd
import numpy as np

print("="*60)
print("DISPOSITIVOS DE ÁUDIO DISPONÍVEIS")
print("="*60)
print(sd.query_devices())
print("\nDispositivo de ENTRADA padrão:", sd.default.device[0])
print("Dispositivo de SAÍDA padrão:", sd.default.device[1])

print("\n" + "="*60)
print("TESTE DE CAPTURA (fale algo por 3 segundos)")
print("="*60)

taxa_amostragem = 16000
audio = sd.rec(int(3 * taxa_amostragem), samplerate=taxa_amostragem, channels=1, dtype='int16')
sd.wait()

volume_medio = np.abs(audio).mean()
volume_maximo = np.abs(audio).max()

print(f"\nVolume médio captado: {volume_medio:.1f}")
print(f"Volume máximo captado: {volume_maximo}")

if volume_medio < 50:
    print("\n⚠️  Volume muito baixo ou nenhum áudio captado.")
    print("   Possíveis causas: microfone errado selecionado, permissão negada, ou mic mudo.")
else:
    print(f"\n✅ Áudio captado! Use um limiar_silencio entre {int(volume_medio * 0.3)} e {int(volume_medio * 0.6)} no burn_com_voz.py")