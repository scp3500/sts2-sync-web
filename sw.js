const CACHE_NAME = 'sts2-sync-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/Data/cards.json',
  '/Resources/ui_atlas_0.png',
  '/Resources/card_atlas_0.png',
  '/Resources/ui_atlas.tpsheet',
  '/Resources/card_atlas.tpsheet',
  '/Resources/fonts/kreon_bold.ttf',
  '/Resources/fonts/zhs/NotoSansMonoCJKsc-Regular.otf'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching core assets');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // 缓存优先策略：如果有缓存就用缓存，没有再联网下载
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).then((fetchRes) => {
        // 如果是资源文件，顺手也存进缓存里
        if (event.request.url.includes('/Resources/') || event.request.url.includes('/Data/')) {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, fetchRes.clone());
            return fetchRes;
          });
        }
        return fetchRes;
      });
    })
  );
});
