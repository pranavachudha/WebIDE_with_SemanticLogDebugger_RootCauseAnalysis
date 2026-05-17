const pendingRequests = new Map();

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // WebWorker requests input synchronously
    if (url.pathname === '/__pyglide_input__') {
        const uid = url.searchParams.get('uid');
        event.respondWith(new Promise((resolve) => {
            pendingRequests.set(uid, resolve);
            
            // Notify the main thread that input is needed
            self.clients.matchAll().then(clients => {
                clients.forEach(client => {
                    client.postMessage({ type: 'input_requested', uid });
                });
            });
        }));
    } 
    // Main thread provides the input asynchronously
    else if (url.pathname === '/__pyglide_provide_input__') {
        event.respondWith((async () => {
            const formData = await event.request.formData();
            const uid = formData.get('uid');
            const value = formData.get('value');
            
            const resolve = pendingRequests.get(uid);
            if (resolve) {
                resolve(new Response(value, { status: 200 }));
                pendingRequests.delete(uid);
            }
            return new Response('ok', { status: 200 });
        })());
    }
});
