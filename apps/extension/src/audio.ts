/** Restore tab playback without changing the original stream sent to MediaRecorder. */
export async function preserveTabAudio(
  stream: MediaStream,
): Promise<() => Promise<void>> {
  if (stream.getAudioTracks().length === 0) return async () => {};
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  try {
    source.connect(context.destination);
    await context.resume();
  } catch (error) {
    source.disconnect();
    await context.close();
    throw error;
  }
  return async () => {
    source.disconnect();
    await context.close();
  };
}
