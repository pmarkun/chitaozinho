/** Mix only into the recording, never into the speaker playback graph. */
export async function addMicrophone(source: MediaStream) {
  const microphone = await navigator.mediaDevices.getUserMedia({
    video: false,
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  let context: AudioContext | undefined;
  let destination: MediaStreamAudioDestinationNode | undefined;
  const nodes: AudioNode[] = [];
  try {
    if (microphone.getAudioTracks().length === 0)
      throw new Error("Microphone provided no audio track");
    context = new AudioContext();
    destination = context.createMediaStreamDestination();
    for (const input of [source, microphone]) {
      if (!input.getAudioTracks().length) continue;
      const node = context.createMediaStreamSource(input);
      const gain = context.createGain();
      gain.gain.value = 0.5;
      node.connect(gain).connect(destination);
      nodes.push(node, gain);
    }
    await context.resume();
    return {
      stream: new MediaStream([
        ...source.getVideoTracks(),
        ...destination.stream.getAudioTracks(),
      ]),
      microphone,
      close: async () => {
        nodes.forEach((node) => node.disconnect());
        microphone.getTracks().forEach((track) => track.stop());
        destination?.stream.getTracks().forEach((track) => track.stop());
        await context?.close();
      },
    };
  } catch (error) {
    nodes.forEach((node) => node.disconnect());
    microphone.getTracks().forEach((track) => track.stop());
    destination?.stream.getTracks().forEach((track) => track.stop());
    await context?.close();
    throw error;
  }
}
