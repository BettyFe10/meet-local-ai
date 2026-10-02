// Client del backend per le pagine dell'estensione e il service worker (porta da chrome.storage.local).
import { BackendError, makeClient, MSG_OFFLINE } from "./http.js";

export { BackendError, MSG_OFFLINE };
export const DEFAULT_PORT = 8765;

export async function getPort() {
  const { backendPort } = await chrome.storage.local.get({ backendPort: DEFAULT_PORT });
  return backendPort;
}

export async function baseUrl() {
  return `http://127.0.0.1:${await getPort()}/api/v1`;
}

const client = makeClient(baseUrl);
export const {
  request, getHealth, listMeetings, getMeeting, getStatus, startMeeting, stopMeeting, renameMeeting, sendChunk,
  getTranscript, getSummary, reprocessMeeting, getAudioToken, audioUrl, openFolder, openDataRoot,
  deleteMeeting, exportMeeting, getStorage,
} = client;
