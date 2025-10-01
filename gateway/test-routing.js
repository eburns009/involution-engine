#!/usr/bin/env node

/**
 * Test script for gateway routing logic
 */

// Mock the routing function for testing
function extractYear(isoDateString) {
    const match = isoDateString.match(/^(-?\d{1,4})-/);
    if (!match) {
        throw new Error('Invalid date format');
    }
    return parseInt(match[1], 10);
}

function routeRequest(birthTime, kernelOverride, userPreferences = {}) {
    const DE440_MIN_YEAR = 1550;
    const DE440_MAX_YEAR = 2650;

    // Explicit kernel override
    if (kernelOverride === 'de441' || kernelOverride === 'DE441') {
        return {
            service: 'DE441_SERVICE',
            kernel: 'DE441',
            reason: 'explicit_override'
        };
    }

    if (kernelOverride === 'de440' || kernelOverride === 'DE440') {
        return {
            service: 'DE440_SERVICE',
            kernel: 'DE440',
            reason: 'explicit_override'
        };
    }

    try {
        const year = extractYear(birthTime);

        // Check if date is within DE440 coverage
        if (year >= DE440_MIN_YEAR && year <= DE440_MAX_YEAR) {
            return {
                service: 'DE440_SERVICE',
                kernel: 'DE440',
                reason: 'optimal_coverage',
                year
            };
        }

        // Date outside DE440 coverage
        if (userPreferences.historicalEnabled) {
            return {
                service: 'DE441_SERVICE',
                kernel: 'DE441',
                reason: 'historical_coverage',
                year
            };
        }

        // Historical pack not enabled
        return {
            needsHistorical: true,
            kernel: 'DE441',
            reason: 'requires_historical_pack',
            year
        };

    } catch (error) {
        return {
            service: 'DE440_SERVICE',
            kernel: 'DE440',
            reason: 'fallback_date_error',
            error: error.message
        };
    }
}

console.log('🧪 Gateway Routing Logic Tests');
console.log('===============================\n');

const testCases = [
    // Modern dates
    { date: '2024-06-21T18:00:00Z', desc: 'Modern date (2024)', expected: 'DE440' },
    { date: '1800-01-01T00:00:00Z', desc: 'Historical in range (1800)', expected: 'DE440' },
    { date: '2500-12-31T23:59:59Z', desc: 'Future in range (2500)', expected: 'DE440' },

    // Out of range dates
    { date: '1066-10-14T12:00:00Z', desc: 'Medieval (1066)', expected: 'NEEDS_HISTORICAL' },
    { date: '3000-01-01T00:00:00Z', desc: 'Far future (3000)', expected: 'NEEDS_HISTORICAL' },
    { date: '-0500-06-21T12:00:00Z', desc: 'Ancient (500 BCE)', expected: 'NEEDS_HISTORICAL' },

    // Edge cases
    { date: '1550-01-01T00:00:00Z', desc: 'DE440 start boundary', expected: 'DE440' },
    { date: '2650-12-31T23:59:59Z', desc: 'DE440 end boundary', expected: 'DE440' },
    { date: '1549-12-31T23:59:59Z', desc: 'Just before DE440 range', expected: 'NEEDS_HISTORICAL' },
    { date: '2651-01-01T00:00:00Z', desc: 'Just after DE440 range', expected: 'NEEDS_HISTORICAL' }
];

testCases.forEach(({ date, desc, expected }) => {
    console.log(`📅 ${desc}:`);
    console.log(`   Date: ${date}`);

    // Test without historical pack
    const result = routeRequest(date, null, { historicalEnabled: false });
    const actual = result.needsHistorical ? 'NEEDS_HISTORICAL' : result.kernel;

    console.log(`   Route: ${actual}`);
    console.log(`   Reason: ${result.reason}`);
    console.log(`   Expected: ${expected}`);
    console.log(`   ${actual === expected ? '✅' : '❌'} ${actual === expected ? 'PASS' : 'FAIL'}`);
    console.log('');
});

console.log('🔧 Override Tests:');
console.log('==================\n');

// Test overrides
const overrideTests = [
    { date: '2024-06-21T18:00:00Z', kernel: 'de441', expected: 'DE441', desc: 'Force DE441 on modern date' },
    { date: '1066-10-14T12:00:00Z', kernel: 'de441', expected: 'DE441', desc: 'Force DE441 on historical date' },
    { date: '3000-01-01T00:00:00Z', kernel: 'de440', expected: 'DE440', desc: 'Force DE440 on future date' }
];

overrideTests.forEach(({ date, kernel, expected, desc }) => {
    console.log(`⚙️  ${desc}:`);
    console.log(`   Date: ${date}, Override: ${kernel}`);

    const result = routeRequest(date, kernel);
    const actual = result.kernel;

    console.log(`   Route: ${actual}`);
    console.log(`   Reason: ${result.reason}`);
    console.log(`   ${actual === expected ? '✅' : '❌'} ${actual === expected ? 'PASS' : 'FAIL'}`);
    console.log('');
});

console.log('🏛️  Historical Pack Tests:');
console.log('===========================\n');

// Test with historical pack enabled
const historicalTests = [
    { date: '1066-10-14T12:00:00Z', enabled: true, expected: 'DE441' },
    { date: '3000-01-01T00:00:00Z', enabled: true, expected: 'DE441' },
    { date: '-0500-06-21T12:00:00Z', enabled: true, expected: 'DE441' }
];

historicalTests.forEach(({ date, enabled, expected }) => {
    const year = extractYear(date);
    console.log(`📚 Historical Pack ${enabled ? 'ENABLED' : 'DISABLED'} - Year ${year}:`);

    const result = routeRequest(date, null, { historicalEnabled: enabled });
    const actual = result.needsHistorical ? 'NEEDS_HISTORICAL' : result.kernel;

    console.log(`   Route: ${actual}`);
    console.log(`   Reason: ${result.reason}`);
    console.log(`   ${actual === expected ? '✅' : '❌'} ${actual === expected ? 'PASS' : 'FAIL'}`);
    console.log('');
});

console.log('✅ Gateway routing logic test complete');