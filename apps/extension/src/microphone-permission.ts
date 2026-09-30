import { documentLanguage, t } from "./i18n";
import "./popup.css";

document.documentElement.lang = documentLanguage(chrome.i18n.getUILanguage());
document.querySelector("#title")!.textContent = t("microphoneTitle");
document.querySelector("#notice")!.textContent = t(
  "microphonePermissionNotice",
);
const button = document.querySelector<HTMLButtonElement>("#authorize")!;
const status = document.querySelector("#status")!;
button.textContent = t("authorizeMicrophone");
button.addEventListener("click", () => {
  button.disabled = true;
  void navigator.mediaDevices.getUserMedia({ audio: true, video: false }).then(
    (stream) => {
      stream.getTracks().forEach((track) => track.stop());
      status.textContent = t("microphonePermissionGranted");
      button.disabled = false;
    },
    () => {
      status.textContent = t("microphonePermissionDenied");
      button.disabled = false;
    },
  );
});
