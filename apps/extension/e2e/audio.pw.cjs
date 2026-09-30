const { expect, test } = require("@playwright/test");

for (const granted of [true, false]) {
  test(`microphone permission probe granted=${granted} never records and stops the probe`, async ({
    browser,
  }) => {
    const context = await browser.newContext();
    await context.addInitScript((allow) => {
      globalThis.probeStopped = false;
      globalThis.chrome = {
        i18n: { getUILanguage: () => "pt-BR", getMessage: (key) => key },
      };
      globalThis.navigator.mediaDevices.getUserMedia = async () => {
        if (!allow) throw new Error("NotAllowedError");
        return {
          getTracks: () => [
            {
              stop: () => {
                globalThis.probeStopped = true;
              },
            },
          ],
        };
      };
      globalThis.MediaRecorder = function () {
        throw new Error("Permission probe must never record");
      };
    }, granted);
    const page = await context.newPage();
    await page.goto("/microphone.html");
    await page.getByRole("button", { name: "authorizeMicrophone" }).click();
    await expect(page.getByRole("status")).toHaveText(
      granted ? "microphonePermissionGranted" : "microphonePermissionDenied",
    );
    expect(await page.evaluate(() => globalThis.probeStopped)).toBe(granted);
    await expect(page.getByRole("button")).toBeEnabled();
    await context.close();
  });
}

test("offscreen recorder produces a WebM with source and microphone tones", async ({
  browser,
}) => {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    globalThis.listeners = [];
    globalThis.chunks = [];
    globalThis.inputs = [];
    globalThis.chrome = {
      runtime: {
        onMessage: {
          addListener: (listener) => globalThis.listeners.push(listener),
        },
        sendMessage: async (message) => {
          if (message.type === "RECORDER_CHUNK")
            globalThis.chunks.push(message.bytesBase64);
          return { ok: true };
        },
      },
    };
    let calls = 0;
    globalThis.navigator.mediaDevices.getUserMedia = async () => {
      const audio = new globalThis.AudioContext();
      await audio.resume();
      const oscillator = audio.createOscillator();
      oscillator.frequency.value = calls++ === 0 ? 500 : 900;
      const destination = audio.createMediaStreamDestination();
      oscillator.connect(destination);
      oscillator.start();
      const stream = destination.stream;
      if (calls === 1) {
        const canvas = document.createElement("canvas");
        canvas.width = 160;
        canvas.height = 90;
        const drawing = canvas.getContext("2d");
        drawing.fillRect(0, 0, 160, 90);
        stream.addTrack(canvas.captureStream(10).getVideoTracks()[0]);
      }
      globalThis.inputs.push({ stream, audio, oscillator });
      return stream;
    };
  });
  const page = await context.newPage();
  await page.goto("/offscreen.html");
  const result = await page.evaluate(async () => {
    const send = (message) =>
      new Promise((resolve) => globalThis.listeners[0](message, {}, resolve));
    const started = await send({
      type: "RECORDER_START",
      streamId: "synthetic",
      sessionId: "synthetic",
      captureSource: "desktop",
      audio: true,
      microphone: true,
    });
    await new Promise((resolve) => globalThis.setTimeout(resolve, 800));
    const stopped = await send({ type: "RECORDER_STOP" });
    const bytes = globalThis.chunks.map((chunk) =>
      Uint8Array.from(
        globalThis.atob(chunk.replaceAll("-", "+").replaceAll("_", "/")),
        (character) => character.charCodeAt(0),
      ),
    );
    const decoder = new globalThis.AudioContext();
    const decoded = await decoder.decodeAudioData(
      await new globalThis.Blob(bytes, { type: "video/webm" }).arrayBuffer(),
    );
    const samples = decoded.getChannelData(0);
    const amplitude = (frequency) => {
      let real = 0,
        imaginary = 0;
      for (let index = 0; index < samples.length; index++) {
        const angle = (2 * Math.PI * frequency * index) / decoded.sampleRate;
        real += samples[index] * Math.cos(angle);
        imaginary += samples[index] * Math.sin(angle);
      }
      return (2 * Math.hypot(real, imaginary)) / samples.length;
    };
    const output = {
      started,
      stopped,
      sourceTone: amplitude(500),
      microphoneTone: amplitude(900),
      tracksStopped: globalThis.inputs.every(({ stream }) =>
        stream.getTracks().every((track) => track.readyState === "ended"),
      ),
    };
    await decoder.close();
    for (const input of globalThis.inputs) {
      input.oscillator.stop();
      await input.audio.close();
    }
    return output;
  });
  expect(result.started).toEqual({
    ok: true,
    result: { audio: true, microphone: true },
  });
  expect(result.stopped).toEqual({ ok: true });
  expect(result.sourceTone).toBeGreaterThan(0.05);
  expect(result.microphoneTone).toBeGreaterThan(0.05);
  expect(result.tracksStopped).toBe(true);
  await context.close();
});
