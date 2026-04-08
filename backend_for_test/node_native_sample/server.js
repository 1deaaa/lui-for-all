const http = require('node:http');

const items = [
  { id: '1', name: 'paper', status: 'draft' },
  { id: '2', name: 'pen', status: 'ready' },
];

function snapshotItems() {
  return items.map((item) => ({ ...item }));
}

function findItem(id) {
  return items.find((item) => item.id === id) || null;
}

function sendJson(res, statusCode, payload) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(payload));
}

function getItems(req, res) {
  sendJson(res, 200, { route: 'GET /api/items', total: items.length, items: snapshotItems() });
}

function createItem(req, res) {
  const id = String(items.length + 1);
  items.push({ id, name: `item-${id}`, status: 'created' });
  sendJson(res, 201, { route: 'POST /api/items', total: items.length });
}

function replaceItem(req, res) {
  const item = findItem('1');
  if (item) {
    item.name = `${item.name}-v2`;
    item.status = 'replaced';
    sendJson(res, 200, { route: 'PUT /api/items/:id', item });
    return;
  }

  items.push({ id: '1', name: 'item-1', status: 'inserted' });
  sendJson(res, 200, { route: 'PUT /api/items/:id', inserted: true, total: items.length });
}

function patchItem(req, res) {
  const item = findItem('1');
  if (!item) {
    sendJson(res, 404, { route: 'PATCH /api/items/:id', missing: true });
    return;
  }

  item.status = 'patched';
  sendJson(res, 200, { route: 'PATCH /api/items/:id', item });
}

function deleteItem(req, res) {
  const index = items.findIndex((item) => item.id === '1');
  if (index >= 0) {
    const removed = items.splice(index, 1)[0];
    sendJson(res, 200, { route: 'DELETE /api/items/:id', removed, total: items.length });
    return;
  }

  sendJson(res, 404, { route: 'DELETE /api/items/:id', removed: false });
}

function healthHead(req, res) {
  res.setHeader('X-Sample-Items', String(items.length));
  res.end();
}

function healthOptions(req, res) {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  sendJson(res, 200, { route: 'OPTIONS /api/health', total: items.length });
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/api/items') {
    return getItems(req, res);
  }

  if (req.method === 'POST' && req.url === '/api/items') {
    return createItem(req, res);
  }

  if (req.method === 'PUT' && req.url === '/api/items/:id') {
    return replaceItem(req, res);
  }

  if (req.method === 'PATCH' && req.url === '/api/items/:id') {
    return patchItem(req, res);
  }

  if (req.method === 'DELETE' && req.url === '/api/items/:id') {
    return deleteItem(req, res);
  }

  if (req.method === 'HEAD' && req.url === '/api/health') {
    return healthHead(req, res);
  }

  if (req.method === 'OPTIONS' && req.url === '/api/health') {
    return healthOptions(req, res);
  }

  res.statusCode = 404;
  res.end('Not Found');
});

if (require.main === module) {
  server.listen(8030);
}

module.exports = { server };
