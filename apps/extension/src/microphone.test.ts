import { afterEach, expect, it, vi } from "vitest";
import { addMicrophone } from "./microphone";
afterEach(() => vi.unstubAllGlobals());

function setup(fail = false, sourceAudio = true) {
  const micTrack = { stop: vi.fn() };
  const outputTrack = { stop: vi.fn() };
  const videoTrack = {};
  const mic = { getAudioTracks: () => [micTrack], getTracks: () => [micTrack] };
  const source = {
    getAudioTracks: () => (sourceAudio ? [{}] : []),
    getVideoTracks: () => [videoTrack],
  };
  const nodes: {
    connect: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
    gain: { value: number };
  }[] = [];
  const node = () => {
    const value = { connect: vi.fn(), disconnect: vi.fn(), gain: { value: 1 } };
    value.connect.mockImplementation(() => value);
    nodes.push(value);
    return value;
  };
  const destination = {
    stream: {
      getAudioTracks: () => [outputTrack],
      getTracks: () => [outputTrack],
    },
  };
  const context = {
    createMediaStreamSource: vi.fn(node),
    createGain: vi.fn(node),
    createMediaStreamDestination: () => destination,
    resume: fail
      ? vi.fn().mockRejectedValue(new Error("resume failed"))
      : vi.fn().mockResolvedValue(undefined),
    close: vi.fn().mockResolvedValue(undefined),
  };
  const getUserMedia = vi.fn().mockResolvedValue(mic);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal(
    "AudioContext",
    vi.fn(function () {
      return context;
    }),
  );
  vi.stubGlobal(
    "MediaStream",
    vi.fn(function (tracks) {
      return { tracks };
    }),
  );
  return {
    source: source as unknown as MediaStream,
    mic,
    micTrack,
    videoTrack,
    outputTrack,
    nodes,
    context,
    getUserMedia,
  };
}
it.each([true, false])(
  "mixes with source audio=%s without connecting microphone to speakers",
  async (sourceAudio) => {
    const data = setup(false, sourceAudio);
    const mixed = await addMicrophone(data.source);
    expect(data.getUserMedia).toHaveBeenCalledWith({
      video: false,
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    expect(data.context.createMediaStreamSource).toHaveBeenCalledTimes(
      sourceAudio ? 2 : 1,
    );
    expect(mixed.stream).toEqual({
      tracks: [data.videoTrack, data.outputTrack],
    });
    expect(
      data.nodes
        .filter((_, index) => index % 2 === 1)
        .every((node) => node.gain.value === 0.5),
    ).toBe(true);
    await mixed.close();
    expect(data.micTrack.stop).toHaveBeenCalledOnce();
    expect(data.outputTrack.stop).toHaveBeenCalledOnce();
    expect(data.context.close).toHaveBeenCalledOnce();
  },
);
it("cleans microphone and context on mixer initialization failure", async () => {
  const data = setup(true);
  await expect(addMicrophone(data.source)).rejects.toThrow("resume failed");
  expect(data.micTrack.stop).toHaveBeenCalledOnce();
  expect(data.context.close).toHaveBeenCalledOnce();
});
it("propagates permission denial without creating an audio graph", async () => {
  const data = setup();
  data.getUserMedia.mockRejectedValue(new Error("NotAllowedError"));
  await expect(addMicrophone(data.source)).rejects.toThrow("NotAllowedError");
  expect(data.context.createMediaStreamSource).not.toHaveBeenCalled();
});
