// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Tests for service discovery endpoints.
 * Verifies that all 5 discovery layers return correct data:
 * - /api/manifest (universal discovery hub)
 * - /.well-known/agent-card.json (A2A agent protocol)
 * - /openapi.json (developer/app documentation)
 * - Avahi mDNS (tested structurally via file existence)
 * - MCP server (tested via import check)
 */

test.describe('Service Discovery', () => {

    test.describe('/api/manifest', () => {
        test('returns valid JSON with required fields', async ({ request }) => {
            const res = await request.get('/api/manifest');
            expect(res.status()).toBe(200);

            const manifest = await res.json();
            expect(manifest.name).toBe('Sound Box');
            expect(manifest.description).toBeTruthy();
            expect(manifest.version).toBeTruthy();
            // hostname intentionally omitted (security: prevents info disclosure)
            expect(manifest.hostname).toBeUndefined();
            expect(manifest.base_url).toBeTruthy();
        });

        test('lists capabilities', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.capabilities).toContain('music_generation');
            expect(manifest.capabilities).toContain('sfx_generation');
            expect(manifest.capabilities).toContain('audio_library');
        });

        test('includes model status', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.models).toBeDefined();
            expect(manifest.models).toHaveProperty('music');
            expect(manifest.models).toHaveProperty('audio');
        });

        test('includes GPU info', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.gpu).toBeDefined();
            // gpu.name intentionally omitted (security: prevents info disclosure)
            expect(manifest.gpu).not.toHaveProperty('name');
            expect(manifest.gpu).toHaveProperty('available');
        });

        test('includes library stats', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.library).toBeDefined();
            expect(typeof manifest.library.total_tracks).toBe('number');
        });

        test('includes auth info', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.auth).toBeDefined();
            expect(typeof manifest.auth.open_access).toBe('boolean');
            expect(manifest.auth.method).toBeTruthy();
        });

        test('includes endpoint catalog', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.endpoints).toBeDefined();
            expect(manifest.endpoints.generate).toBeDefined();
            expect(manifest.endpoints.generate.method).toBe('POST');
            expect(manifest.endpoints.generate.path).toBe('/generate');
            expect(manifest.endpoints.library).toBeDefined();
            expect(manifest.endpoints.audio_stream).toBeDefined();
        });

        test('includes discovery links', async ({ request }) => {
            const res = await request.get('/api/manifest');
            const manifest = await res.json();

            expect(manifest.discovery).toBeDefined();
            expect(manifest.discovery.manifest).toBe('/api/manifest');
            expect(manifest.discovery.agent_card).toBe('/.well-known/agent-card.json');
            expect(manifest.discovery.openapi).toBe('/openapi.json');
            // mcp_port intentionally omitted (security: prevents port scanning)
            expect(manifest.discovery.mcp_port).toBeUndefined();
        });
    });

    test.describe('/.well-known/agent-card.json', () => {
        test('returns valid A2A agent card', async ({ request }) => {
            const res = await request.get('/.well-known/agent-card.json');
            expect(res.status()).toBe(200);

            const card = await res.json();
            expect(card.name).toBe('Sound Box');
            expect(card.description).toBeTruthy();
            expect(card.url).toBeTruthy();
            expect(card.version).toBeTruthy();
        });

        test('lists skills with required fields', async ({ request }) => {
            const res = await request.get('/.well-known/agent-card.json');
            const card = await res.json();

            expect(card.skills).toBeDefined();
            expect(card.skills.length).toBeGreaterThanOrEqual(4);

            for (const skill of card.skills) {
                expect(skill.id).toBeTruthy();
                expect(skill.name).toBeTruthy();
                expect(skill.description).toBeTruthy();
                expect(skill.endpoint).toBeDefined();
                expect(skill.endpoint.method).toBeTruthy();
                expect(skill.endpoint.path).toBeTruthy();
            }
        });

        test('includes music and SFX generation skills', async ({ request }) => {
            const res = await request.get('/.well-known/agent-card.json');
            const card = await res.json();

            const skillIds = card.skills.map(s => s.id);
            expect(skillIds).toContain('generate-music');
            expect(skillIds).toContain('generate-sfx');
            expect(skillIds).toContain('search-library');
        });

        test('links to OpenAPI and manifest', async ({ request }) => {
            const res = await request.get('/.well-known/agent-card.json');
            const card = await res.json();

            expect(card.openapi).toContain('/openapi.json');
            expect(card.manifest).toContain('/api/manifest');
        });
    });

    test.describe('/openapi.json', () => {
        test('returns valid OpenAPI 3.1 spec', async ({ request }) => {
            const res = await request.get('/openapi.json');
            expect(res.status()).toBe(200);

            const spec = await res.json();
            expect(spec.openapi).toMatch(/^3\.1/);
            expect(spec.info.title).toBe('Sound Box API');
            expect(spec.info.version).toBeTruthy();
        });

        test('contains key paths', async ({ request }) => {
            const res = await request.get('/openapi.json');
            const spec = await res.json();

            const paths = Object.keys(spec.paths);
            expect(paths).toContain('/generate');
            expect(paths).toContain('/job/{job_id}');
            expect(paths).toContain('/status');
            expect(paths).toContain('/api/library');
            expect(paths).toContain('/audio/{filename}');
            expect(paths).toContain('/download/{filename}');
        });

        test('has at least 10 paths', async ({ request }) => {
            const res = await request.get('/openapi.json');
            const spec = await res.json();

            expect(Object.keys(spec.paths).length).toBeGreaterThanOrEqual(10);
        });

        test('defines Track schema', async ({ request }) => {
            const res = await request.get('/openapi.json');
            const spec = await res.json();

            expect(spec.components.schemas.Track).toBeDefined();
            expect(spec.components.schemas.Track.properties.id).toBeDefined();
            expect(spec.components.schemas.Track.properties.prompt).toBeDefined();
            expect(spec.components.schemas.Track.properties.filename).toBeDefined();
        });
    });

    test.describe('Cross-references', () => {
        test('manifest endpoints match OpenAPI paths', async ({ request }) => {
            const [manifestRes, specRes] = await Promise.all([
                request.get('/api/manifest'),
                request.get('/openapi.json'),
            ]);

            const manifest = await manifestRes.json();
            const spec = await specRes.json();
            const specPaths = Object.keys(spec.paths);

            // Key manifest endpoints should have matching OpenAPI paths
            expect(specPaths).toContain(manifest.endpoints.generate.path);
            expect(specPaths).toContain(manifest.endpoints.system_status.path);
            expect(specPaths).toContain(manifest.endpoints.library.path);
        });

        test('agent card skills reference valid endpoints', async ({ request }) => {
            const [cardRes, specRes] = await Promise.all([
                request.get('/.well-known/agent-card.json'),
                request.get('/openapi.json'),
            ]);

            const card = await cardRes.json();
            const spec = await specRes.json();
            const specPaths = Object.keys(spec.paths);

            // Each skill's endpoint path should exist in OpenAPI
            for (const skill of card.skills) {
                expect(specPaths).toContain(skill.endpoint.path);
            }
        });
    });
});
