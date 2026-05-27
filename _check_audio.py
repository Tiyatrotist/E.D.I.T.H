import pyaudio
pa = pyaudio.PyAudio()
print("=== Audio Devices ===")
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0 or info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}  in={info['maxInputChannels']} out={info['maxOutputChannels']} rate={int(info['defaultSampleRate'])}")
print()
try:
    di = pa.get_default_input_device_info()
    print(f"Default Input:  [{di['index']}] {di['name']}")
except Exception as e:
    print(f"Default Input:  ERROR - {e}")
try:
    do = pa.get_default_output_device_info()
    print(f"Default Output: [{do['index']}] {do['name']}")
except Exception as e:
    print(f"Default Output: ERROR - {e}")
pa.terminate()
