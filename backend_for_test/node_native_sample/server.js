const http = require('node:http');

const routes = [];

const router = {
  get(path, handler) {
    routes.push({ method: 'GET', path, handler });
  },
  post(path, handler) {
    routes.push({ method: 'POST', path, handler });
  },
  put(path, handler) {
    routes.push({ method: 'PUT', path, handler });
  },
  patch(path, handler) {
    routes.push({ method: 'PATCH', path, handler });
  },
  delete(path, handler) {
    routes.push({ method: 'DELETE', path, handler });
  },
  head(path, handler) {
    routes.push({ method: 'HEAD', path, handler });
  },
  options(path, handler) {
    routes.push({ method: 'OPTIONS', path, handler });
  },
};

router.get('/api/items', function getItems(req, res) {
  res.end('GET /api/items');
});

router.post('/api/items', function createItem(req, res) {
  res.end('POST /api/items');
});

router.put('/api/items/:id', function replaceItem(req, res) {
  res.end('PUT /api/items/:id');
});

router.patch('/api/items/:id', function patchItem(req, res) {
  res.end('PATCH /api/items/:id');
});

router.delete('/api/items/:id', function deleteItem(req, res) {
  res.end('DELETE /api/items/:id');
});

router.head('/api/health', function healthHead(req, res) {
  res.end();
});

router.options('/api/health', function healthOptions(req, res) {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  res.end();
});

const server = http.createServer((req, res) => {
  const route = routes.find((item) => item.method === req.method && item.path === req.url);
  if (!route) {
    res.statusCode = 404;
    res.end('Not Found');
    return;
  }
  route.handler(req, res);
});

if (require.main === module) {
  server.listen(8030);
}

module.exports = { server, router, routes };
