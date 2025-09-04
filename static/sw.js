const CACHE_NAME = 'biryani-club-v2';
const urlsToCache = [
    '/',
    '/menu',
    '/cart',
    '/login',
    '/register',
    '/static/manifest.json',
    '/static/style.css',
    // Bootstrap CSS
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    // Font Awesome
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    // Google Fonts
    'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap',
    // Bootstrap JS
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Install Service Worker
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch event with improved caching strategy
self.addEventListener('fetch', function(event) {
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {
                // Return cached version or fetch from network
                if (response) {
                    // For HTML pages, try network first for fresh content
                    if (event.request.destination === 'document') {
                        return fetchAndCache(event.request).catch(() => response);
                    }
                    return response;
                }
                
                return fetchAndCache(event.request);
            })
    );
});

function fetchAndCache(request) {
    return fetch(request).then(function(response) {
        // Check if we received a valid response
        if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
        }
        
        // Clone the response because it's a stream
        var responseToCache = response.clone();
        
        // Cache successful responses
        caches.open(CACHE_NAME)
            .then(function(cache) {
                // Only cache GET requests
                if (request.method === 'GET') {
                    cache.put(request, responseToCache);
                }
            });
        
        return response;
    });
}

// Activate Service Worker
self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    // Delete old caches
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Background Sync for offline functionality
self.addEventListener('sync', function(event) {
    if (event.tag === 'background-sync') {
        console.log('Background sync triggered');
        event.waitUntil(doBackgroundSync());
    }
});

function doBackgroundSync() {
    return new Promise(function(resolve) {
        console.log('Syncing offline data...');
        resolve();
    });
}

// Push notifications for order updates
self.addEventListener('push', function(event) {
    const options = {
        body: 'Your order status has been updated!',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🍛</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🍛</text></svg>',
        data: {
            url: '/my_orders'
        },
        actions: [
            {
                action: 'view',
                title: 'View Orders'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ],
        tag: 'order-update',
        requireInteraction: true
    };

    event.waitUntil(
        self.registration.showNotification('Biryani Club', options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    if (event.action === 'view') {
        event.waitUntil(
            clients.openWindow(event.notification.data.url)
        );
    } else if (event.action === 'dismiss') {
        // Just close the notification
        return;
    } else {
        // Default action - open the app
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Handle message events from the main thread
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Network-first strategy for API calls
function networkFirst(request) {
    return fetch(request).then(response => {
        if (response.ok) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
                cache.put(request, responseClone);
            });
        }
        return response;
    }).catch(() => {
        return caches.match(request);
    });
}

// Cache-first strategy for static assets
function cacheFirst(request) {
    return caches.match(request).then(response => {
        if (response) {
            return response;
        }
        return fetch(request).then(response => {
            if (response.ok) {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(request, responseClone);
                });
            }
            return response;
        });
    });
}

// Handle offline functionality
self.addEventListener('online', function(event) {
    console.log('App is back online');
    // Trigger any pending sync operations
    self.registration.sync.register('background-sync');
});

self.addEventListener('offline', function(event) {
    console.log('App is now offline');
});
