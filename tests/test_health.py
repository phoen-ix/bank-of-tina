def test_health_returns_ok(client, app):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'checks' in data
    assert data['checks']['database'] == 'ok'
    assert 'scheduler' in data['checks']
    assert 'icons_writable' in data['checks']


def test_health_json_format(client, app):
    response = client.get('/health')
    assert response.content_type.startswith('application/json')
    data = response.get_json()
    assert 'status' in data
    assert 'checks' in data


def test_csp_header(client, app):
    """CSP header is present on HTML responses with a valid nonce."""
    response = client.get('/')
    assert response.status_code == 200
    csp = response.headers.get('Content-Security-Policy')
    assert csp is not None
    assert "script-src 'self' 'nonce-" in csp
    assert "default-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp


def test_csp_not_on_json(client, app):
    """CSP header should not appear on JSON responses."""
    response = client.get('/health')
    csp = response.headers.get('Content-Security-Policy')
    assert csp is None
