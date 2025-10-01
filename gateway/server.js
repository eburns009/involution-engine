const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Service endpoints
const DE440_SERVICE = process.env.DE440_SERVICE || 'http://127.0.0.1:8000';
const DE441_SERVICE = process.env.DE441_SERVICE || 'http://127.0.0.1:8001';

// DE440 coverage: 1550-2650 CE
const DE440_MIN_YEAR = 1550;
const DE440_MAX_YEAR = 2650;

app.use(cors());
app.use(express.json());

/**
 * Extract year from ISO date string
 * Handles both positive and negative years (BCE dates)
 */
function extractYear(isoDateString) {
    // Handle negative years (BCE): "-0500-06-21T12:00:00Z" -> -500
    const match = isoDateString.match(/^(-?\d{1,4})-/);
    if (!match) {
        throw new Error('Invalid date format');
    }
    return parseInt(match[1], 10);
}

/**
 * Determine which ephemeris service to use based on date and overrides
 */
function routeRequest(birthTime, kernelOverride, userPreferences = {}) {
    // Explicit kernel override
    if (kernelOverride === 'de441' || kernelOverride === 'DE441') {
        return {
            service: DE441_SERVICE,
            kernel: 'DE441',
            reason: 'explicit_override'
        };
    }

    if (kernelOverride === 'de440' || kernelOverride === 'DE440') {
        return {
            service: DE440_SERVICE,
            kernel: 'DE440',
            reason: 'explicit_override'
        };
    }

    try {
        const year = extractYear(birthTime);

        // Check if date is within DE440 coverage
        if (year >= DE440_MIN_YEAR && year <= DE440_MAX_YEAR) {
            return {
                service: DE440_SERVICE,
                kernel: 'DE440',
                reason: 'optimal_coverage',
                year
            };
        }

        // Date outside DE440 coverage
        if (userPreferences.historicalEnabled) {
            return {
                service: DE441_SERVICE,
                kernel: 'DE441',
                reason: 'historical_coverage',
                year
            };
        }

        // Historical pack not enabled - return suggestion
        return {
            needsHistorical: true,
            kernel: 'DE441',
            reason: 'requires_historical_pack',
            year,
            coverage: {
                de440: `${DE440_MIN_YEAR}-${DE440_MAX_YEAR} CE`,
                de441: '13201 BCE - 17191 CE'
            }
        };

    } catch (error) {
        // Fallback to DE440 for date parsing errors
        return {
            service: DE440_SERVICE,
            kernel: 'DE440',
            reason: 'fallback_date_error',
            error: error.message
        };
    }
}

/**
 * Proxy request to appropriate ephemeris service
 */
async function proxyToService(serviceUrl, path, body, headers) {
    const url = `${serviceUrl}${path}`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...headers
        },
        body: JSON.stringify(body)
    });

    const data = await response.json();
    return { data, status: response.status, headers: response.headers };
}

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        gateway: 'involution-ephemeris-router',
        services: {
            de440: DE440_SERVICE,
            de441: DE441_SERVICE
        },
        coverage: {
            de440: `${DE440_MIN_YEAR}-${DE440_MAX_YEAR} CE`,
            de441: '13201 BCE - 17191 CE'
        }
    });
});

// Calculation endpoint with smart routing
app.post('/calculate', async (req, res) => {
    try {
        const { birth_time, ...otherParams } = req.body;
        const kernelOverride = req.query.kernel || req.body.kernel;
        const historicalEnabled = req.headers['x-historical-enabled'] === 'true';

        if (!birth_time) {
            return res.status(400).json({
                error: 'birth_time is required'
            });
        }

        // Determine routing
        const routing = routeRequest(birth_time, kernelOverride, { historicalEnabled });

        // Handle historical pack required case
        if (routing.needsHistorical) {
            return res.status(422).json({
                error: 'Historical ephemeris required',
                details: {
                    requested_year: routing.year,
                    available_coverage: routing.coverage,
                    solutions: [
                        'Enable Historical Pack in settings',
                        'Add ?kernel=de441 to request',
                        'Add header: x-historical-enabled: true'
                    ]
                },
                code: 'HISTORICAL_REQUIRED'
            });
        }

        // Add routing metadata to request
        const enhancedBody = {
            ...req.body,
            _gateway_routing: {
                selected_kernel: routing.kernel,
                reason: routing.reason,
                year: routing.year
            }
        };

        // Proxy to selected service
        const result = await proxyToService(
            routing.service,
            '/calculate',
            enhancedBody,
            req.headers
        );

        // Enhance response with routing information
        if (result.data.meta) {
            result.data.meta.gateway_routing = {
                selected_kernel: routing.kernel,
                reason: routing.reason,
                year: routing.year,
                service_url: routing.service
            };
        }

        res.status(result.status).json(result.data);

    } catch (error) {
        console.error('Gateway error:', error);
        res.status(500).json({
            error: 'Gateway routing failed',
            details: error.message
        });
    }
});

// Houses endpoint with smart routing (same logic)
app.post('/houses', async (req, res) => {
    try {
        const { birth_time } = req.body;
        const kernelOverride = req.query.kernel;
        const historicalEnabled = req.headers['x-historical-enabled'] === 'true';

        if (!birth_time) {
            return res.status(400).json({ error: 'birth_time is required' });
        }

        const routing = routeRequest(birth_time, kernelOverride, { historicalEnabled });

        if (routing.needsHistorical) {
            return res.status(422).json({
                error: 'Historical ephemeris required',
                details: {
                    requested_year: routing.year,
                    available_coverage: routing.coverage
                },
                code: 'HISTORICAL_REQUIRED'
            });
        }

        const result = await proxyToService(routing.service, '/houses', req.body, req.headers);
        res.status(result.status).json(result.data);

    } catch (error) {
        console.error('Gateway error:', error);
        res.status(500).json({ error: 'Gateway routing failed', details: error.message });
    }
});

// Passthrough endpoints for service info
app.get('/info/:kernel?', async (req, res) => {
    try {
        const kernel = req.params.kernel || 'de440';
        const serviceUrl = kernel.toLowerCase() === 'de441' ? DE441_SERVICE : DE440_SERVICE;

        const response = await fetch(`${serviceUrl}/info`);
        const data = await response.json();

        res.json(data);
    } catch (error) {
        res.status(500).json({ error: 'Failed to fetch service info' });
    }
});

// Documentation endpoint
app.get('/routing', (req, res) => {
    res.json({
        description: 'Involution Ephemeris Gateway - Smart Routing',
        routing_rules: [
            {
                condition: 'Date within 1550-2650 CE',
                target: 'DE440 service (port 8000)',
                reason: 'Optimal coverage and performance'
            },
            {
                condition: 'Date outside 1550-2650 CE + historical enabled',
                target: 'DE441 service (port 8001)',
                reason: 'Extended historical coverage'
            },
            {
                condition: 'Date outside 1550-2650 CE + historical disabled',
                target: 'Error response',
                reason: 'Prompt user to enable historical pack'
            }
        ],
        overrides: [
            '?kernel=de440 - Force DE440',
            '?kernel=de441 - Force DE441',
            'x-historical-enabled: true - Auto-enable DE441 for out-of-range dates'
        ],
        examples: [
            'POST /calculate - Auto-route based on birth_time',
            'POST /calculate?kernel=de441 - Force historical ephemeris',
            'GET /info/de440 - Get DE440 service info',
            'GET /info/de441 - Get DE441 service info'
        ]
    });
});

app.listen(PORT, () => {
    console.log(`🌟 Involution Gateway running on port ${PORT}`);
    console.log(`📡 DE440 service: ${DE440_SERVICE}`);
    console.log(`📡 DE441 service: ${DE441_SERVICE}`);
    console.log(`🔀 Smart routing: ${DE440_MIN_YEAR}-${DE440_MAX_YEAR} CE → DE440, else → DE441`);
});

module.exports = app;