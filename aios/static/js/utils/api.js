/**
 * API Utility Client wrapper for token authentication and streaming responses.
 */

const API_BASE = '/api';

function getHeaders() {
  const token = localStorage.getItem('aios_token');
  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const mergedOptions = {
    ...options,
    headers: {
      ...getHeaders(),
      ...options.headers,
    },
  };

  const response = await fetch(url, mergedOptions);
  
  if (response.status === 401) {
    // Session expired or unauthorized
    localStorage.removeItem('aios_token');
    window.location.reload();
    throw new Error('Unauthorized/Expired Session');
  }
  
  if (!response.ok) {
    const text = await response.text();
    let err = text;
    try {
      const json = JSON.parse(text);
      err = json.detail || json.message || text;
    } catch(e) {}
    throw new Error(err);
  }

  return response.json();
}

async function apiForm(endpoint, formData, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = localStorage.getItem('aios_token');
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('aios_token');
    window.location.reload();
    throw new Error('Unauthorized/Expired Session');
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text);
  }

  return response.json();
}

/**
 * Custom SSE reader that supports POST requests and custom headers (JWT).
 * Utilizes the streams API to read chunk-by-chunk.
 */
async function apiStream(endpoint, body, onEvent) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(body)
  });

  if (response.status === 401) {
    localStorage.removeItem('aios_token');
    window.location.reload();
    throw new Error('Unauthorized/Expired Session');
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    
    // Parse SSE frames from buffer
    const lines = buffer.split('\n');
    // Save the last partial line back to the buffer
    buffer = lines.pop();

    let currentEvent = null;
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith('event:')) {
        currentEvent = trimmed.replace('event:', '').trim();
      } else if (trimmed.startsWith('data:') && currentEvent) {
        const rawData = trimmed.replace('data:', '').trim();
        try {
          const parsedData = JSON.parse(rawData);
          onEvent({ event: currentEvent, data: parsedData });
        } catch (e) {
          onEvent({ event: currentEvent, data: rawData });
        }
        currentEvent = null; // reset
      }
    }
  }
}

export default apiFetch;
export { apiForm, apiStream };

