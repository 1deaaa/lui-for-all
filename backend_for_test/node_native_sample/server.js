const http = require('node:http');

function getItems(req, res) {
  res.end('GET /api/items');
}

function createItem(req, res) {
  res.end('POST /api/items');
}

function replaceItem(req, res) {
  res.end('PUT /api/items/:id');
}

function patchItem(req, res) {
  res.end('PATCH /api/items/:id');
}

function deleteItem(req, res) {
  res.end('DELETE /api/items/:id');
}

function healthHead(req, res) {
  res.end();
}

function healthOptions(req, res) {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  res.end();
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
