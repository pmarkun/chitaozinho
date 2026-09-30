import { afterEach, describe, expect, it, vi } from "vitest";
import { preserveTabAudio } from "./audio";

afterEach(() => vi.unstubAllGlobals());

describe("tab audio playback", () => {
  function setup(fail = false) {
    const source = { connect: vi.fn(), disconnect: vi.fn() };
    const context = {
      destination: {},
      createMediaStreamSource: vi.fn(() => source),
      resume: fail
        ? vi.fn().mockRejectedValue(new Error("audio denied"))
        : vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
    };
    const Constructor = vi.fn(function () {
      return context;
    });
    vi.stubGlobal("AudioContext", Constructor);
    return { source, context, Constructor };
  }
  it("plays the captured stream and releases the output on stop", async () => {
    const { source, context } = setup();
    const stream = { getAudioTracks: () => [{}] } as MediaStream;
    const close = await preserveTabAudio(stream);
    expect(context.createMediaStreamSource).toHaveBeenCalledWith(stream);
    expect(source.connect).toHaveBeenCalledWith(context.destination);
    expect(context.resume).toHaveBeenCalledOnce();
    await close();
    expect(source.disconnect).toHaveBeenCalledOnce();
    expect(context.close).toHaveBeenCalledOnce();
  });
  it("does not create an output for a silent stream", async () => {
    const { Constructor } = setup();
    await (
      await preserveTabAudio({
        getAudioTracks: () => [],
      } as unknown as MediaStream)
    )();
    expect(Constructor).not.toHaveBeenCalled();
  });
  it("cleans up and reports playback initialization failures", async () => {
    const { source, context } = setup(true);
    await expect(
      preserveTabAudio({ getAudioTracks: () => [{}] } as MediaStream),
    ).rejects.toThrow("audio denied");
    expect(source.disconnect).toHaveBeenCalledOnce();
    expect(context.close).toHaveBeenCalledOnce();
  });
});
