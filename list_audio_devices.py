from jarvis.modules.voice import VoiceSystem


def main():
    voice = VoiceSystem({"system": {}, "voice": {}})
    devices = voice.list_input_devices()
    if not devices:
        print("No input devices found.")
        return

    print("Available input devices:")
    for device in devices:
        print(
            f"[{device['index']}] {device['name']} "
            f"(defaultSampleRate={device['defaultSampleRate']} Hz)"
        )


if __name__ == "__main__":
    main()
