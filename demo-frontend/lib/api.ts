import axios, { AxiosError } from "axios";
import type { ChatRequest, ChatResponse, HistoryEntry } from "@/types";

// Requests are proxied through Next.js (/backend/* → FastAPI) to avoid CORS.
const api = axios.create({
  baseURL: "/backend",
  timeout: 45_000,
  headers: { "Content-Type": "application/json" },
});

/**
 * Send a message to the AI receptionist.
 *
 * @param message   - The user's current message.
 * @param history   - Previous turns (excludes the initial greeting).
 * @returns The assistant's reply text.
 * @throws A human-readable error string on failure.
 */
export async function sendMessage(
  message: string,
  history: HistoryEntry[] = []
): Promise<string> {
  try {
    const payload: ChatRequest = { message, history };
    const { data } = await api.post<ChatResponse>("/api/v1/demo/chat", payload);
    return data.reply;
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const axiosErr = err as AxiosError;

      if (axiosErr.code === "ECONNABORTED") {
        throw new Error(
          "The request timed out. The AI is taking too long to respond — please try again."
        );
      }
      if (!axiosErr.response) {
        throw new Error(
          "Cannot reach the backend. Make sure the FastAPI server is running on port 8000."
        );
      }
      if (axiosErr.response.status >= 500) {
        throw new Error(
          `Server error (${axiosErr.response.status}). Check the backend logs for details.`
        );
      }
      throw new Error(`Request failed: ${axiosErr.response.status}`);
    }
    throw new Error("An unexpected error occurred. Please try again.");
  }
}
