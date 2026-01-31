import {apiFetch} from "./client";

export async function fetchSpaces() {
    return apiFetch("/spaces");
}