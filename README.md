# 🏗️ Involution Engine - Foundation Steps with Intelligent Ephemeris Switching

## 🎯 **Foundation Philosophy: Multi-Ephemeris Strategy**

We'll implement **intelligent ephemeris source switching** based on date ranges for optimal accuracy and performance:

- **Swiss .se1 (compressed DE431)**: Default for speed and general accuracy
- **JPL DE440**: Highest accuracy for modern dates (1550–2650 CE)  
- **JPL DE441**: Extended range for deep past/future calculations
- **Auto-switching logic**: Seamless transitions based on Julian Day ranges

## 📋 **Foundation Architecture: Smart Ephemeris Layer**

```
┌─────────────────────────────────────────────────────────┐
│  Step 4: Production API (Complete System)              │
│  ├── Single /calculate endpoint with auto-switching    │
│  ├── Comprehensive error handling                      │
│  └── Full health checks & monitoring                   │
├─────────────────────────────────────────────────────────┤
│  Step 3: Security Foundation                           │
│  ├── OAuth 2.0 + PKCE authentication                   │
│  ├── RS256 JWT with 15-min expiration                  │
│  └── Input validation & rate limiting                   │
├─────────────────────────────────────────────────────────┤
│  Step 2: Performance & Caching                         │
│  ├── Intelligent cache keying by ephemeris source      │
│  ├── Smart TTL based on accuracy requirements          │
│  └── Cache-miss performance optimization                │
├─────────────────────────────────────────────────────────┤
│  Step 1: Multi-Ephemeris Core Engine                   │
│  ├── Swiss .se1 integration (primary)                  │
│  ├── JPL DE440/DE441 integration                       │
│  ├── Auto-switching logic by date range                │
│  └── Cross-validation between sources                   │
└─────────────────────────────────────────────────────────┘
```

## 🔧 **Step 1: Multi-Ephemeris Core Engine**

### **Goal: Intelligent Ephemeris Selection with Cross-Validation**

#### **1. Ephemeris Source Manager**
```typescript
// src/core/ephemeris-manager.ts
import swisseph from 'swisseph';
import { createModuleLogger } from '@utils/logger.js';

const logger = createModuleLogger('ephemeris-manager');

interface EphemerisSource {
  name: string;
  type: 'swiss' | 'jpl';
  accuracy: number; // arcseconds
  dateRangeStart: number; // Julian Day
  dateRangeEnd: number;   // Julian Day
  files: string[];
  priority: number; // Higher = preferred
}

const EPHEMERIS_SOURCES: EphemerisSource[] = [
  {
    name: 'Swiss SE1 (DE431 Compressed)',
    type: 'swiss',
    accuracy: 0.5, // Sub-arcsecond for most purposes
    dateRangeStart: 1721425.5, // Jan 1, 1 CE
    dateRangeEnd: 5373484.5,   // Jan 1, 10000 CE
    files: ['sepl_30.se1', 'semo_30.se1', 'seas_30.se1'],
    priority: 1, // Default choice for speed
  },
  {
    name: 'JPL DE440 (High Accuracy Modern)',
    type: 'jpl',
    accuracy: 0.001, // Sub-milliarcsecond precision
    dateRangeStart: 2305424.5, // Jan 1, 1550 CE
    dateRangeEnd: 2816787.5,   // Jan 1, 2650 CE  
    files: ['de440.bsp'],
    priority: 3, // Highest accuracy for modern dates
  },
  {
    name: 'JPL DE441 (Extended Range)',
    type: 'jpl', 
    accuracy: 0.01, // High accuracy, wider range
    dateRangeStart: 1721425.5, // Jan 1, 1 CE
    dateRangeEnd: 5373484.5,   // Jan 1, 10000 CE
    files: ['de441.bsp'],
    priority: 2, // High accuracy for extended dates
  },
];

export class EphemerisManager {
  private availableSources: Map<string, EphemerisSource> = new Map();
  private isInitialized = false;

  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    logger.info('Initializing ephemeris sources...');

    for (const source of EPHEMERIS_SOURCES) {
      try {
        await this.validateEphemerisSource(source);
        this.availableSources.set(source.name, source);
        logger.info(`✅ ${source.name} available`);
      } catch (error) {
        logger.warn(`⚠️ ${source.name} not available: ${error.message}`);
      }
    }

    if (this.availableSources.size === 0) {
      throw new Error('No ephemeris sources available');
    }

    this.isInitialized = true;
    logger.info(`Ephemeris manager initialized with ${this.availableSources.size} sources`);
  }

  selectOptimalSource(julianDay: number, requestedAccuracy?: number): EphemerisSource {
    if (!this.isInitialized) {
      throw new Error('Ephemeris manager not initialized');
    }

    // Filter sources that cover the requested date
    const validSources = Array.from(this.availableSources.values())
      .filter(source => 
        julianDay >= source.dateRangeStart && 
        julianDay <= source.dateRangeEnd
      );

    if (validSources.length === 0) {
      throw new Error(`No ephemeris data available for Julian Day ${julianDay}`);
    }

    // If specific accuracy requested, filter by capability
    if (requestedAccuracy) {
      const accurateSources = validSources.filter(s => s.accuracy <= requestedAccuracy);
      if (accurateSources.length > 0) {
        // Return highest priority source that meets accuracy requirement
        return accurateSources.sort((a, b) => b.priority - a.priority)[0];
      }
    }

    // Auto-selection logic based on date and accuracy
    const modernDateRange = julianDay >= 2305424.5 && julianDay <= 2816787.5; // 1550-2650 CE

    if (modernDateRange && this.availableSources.has('JPL DE440 (High Accuracy Modern)')) {
      // Use JPL DE440 for highest accuracy in modern era
      return this.availableSources.get('JPL DE440 (High Accuracy Modern)')!;
    }

    if (this.availableSources.has('JPL DE441 (Extended Range)')) {
      // Use JPL DE441 for high accuracy across extended range
      return this.availableSources.get('JPL DE441 (Extended Range)')!;
    }

    // Fallback to Swiss SE1 for speed
    return validSources.sort((a, b) => b.priority - a.priority)[0];
  }

  private async validateEphemerisSource(source: EphemerisSource): Promise<void> {
    // Check if ephemeris files exist and are readable
    const ephemerisPath = process.env.EPHEMERIS_PATH || './data/ephemeris';
    
    if (source.type === 'swiss') {
      // Validate Swiss ephemeris files
      for (const file of source.files) {
        const filePath = `${ephemerisPath}/${file}`;
        try {
          // Test Swiss ephemeris file access
          swisseph.swe_set_ephe_path(ephemerisPath);
          const testCalc = swisseph.swe_calc_ut(2451545.0, 0, swisseph.SEFLG_SWIEPH);
          if (testCalc.error) {
            throw new Error(`Swiss ephemeris test failed: ${testCalc.error}`);
          }
        } catch (error) {
          throw new Error(`Swiss ephemeris validation failed: ${error.message}`);
        }
      }
    } else if (source.type === 'jpl') {
      // Validate JPL ephemeris files
      for (const file of source.files) {
        const filePath = `${ephemerisPath}/jpl/${file}`;
        try {
          // Test JPL file exists and is readable
          const fs = await import('fs/promises');
          await fs.access(filePath);
          
          // TODO: Add actual JPL ephemeris validation
          // This would require JPL SPICE toolkit integration
          logger.info(`JPL file ${file} exists (validation pending SPICE integration)`);
        } catch (error) {
          throw new Error(`JPL ephemeris file not found: ${filePath}`);
        }
      }
    }
  }

  getAvailableSources(): EphemerisSource[] {
    return Array.from(this.availableSources.values());
  }

  getSourceInfo(): Record<string, any> {
    return {
      initialized: this.isInitialized,
      availableCount: this.availableSources.size,
      sources: Array.from(this.availableSources.values()).map(s => ({
        name: s.name,
        type: s.type,
        accuracy: s.accuracy,
        dateRange: {
          start: s.dateRangeStart,
          end: s.dateRangeEnd,
        },
        priority: s.priority,
      })),
    };
  }
}
```

#### **2. Enhanced Swiss Engine with Source Selection**
```typescript
// src/core/enhanced-swiss-engine.ts
import swisseph from 'swisseph';
import { EphemerisManager } from './ephemeris-manager.js';
import { createModuleLogger } from '@utils/logger.js';

const logger = createModuleLogger('enhanced-swiss-engine');

interface CalculationParams {
  julianDay: number;
  body: number;
  flags?: number;
  requestedAccuracy?: number; // arcseconds
  preferredSource?: string;
}

interface EnhancedPosition {
  longitude: number;
  latitude: number;
  distance: number;
  speed: number;
  calculationTime: number;
  accuracy: number;
  ephemerisSource: string;
  sourceType: 'swiss' | 'jpl';
  crossValidated?: boolean;
  validationDiscrepancy?: number;
}

export class EnhancedSwissEngine {
  private ephemerisManager: EphemerisManager;
  private isInitialized = false;

  constructor() {
    this.ephemerisManager = new EphemerisManager();
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      await this.ephemerisManager.initialize();
      
      // Test calculation with optimal source selection
      const testResult = await this.calculatePosition({
        julianDay: 2451545.0, // J2000.0
        body: 0, // Sun
      });

      // Validate against expected result
      const expectedLongitude = 280.16; // Approximate
      const tolerance = 1.0; // 1 degree tolerance for validation

      if (Math.abs(testResult.longitude - expectedLongitude) > tolerance) {
        throw new Error(`Engine validation failed. Expected ~${expectedLongitude}°, got ${testResult.longitude}°`);
      }

      this.isInitialized = true;
      logger.info('✅ Enhanced Swiss engine initialized with multi-ephemeris support');
      
    } catch (error) {
      logger.error('❌ Enhanced Swiss engine initialization failed:', error);
      throw error;
    }
  }

  async calculatePosition(params: CalculationParams): Promise<EnhancedPosition> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    const startTime = Date.now();

    try {
      // Select optimal ephemeris source
      const source = this.ephemerisManager.selectOptimalSource(
        params.julianDay, 
        params.requestedAccuracy
      );

      logger.debug('Selected ephemeris source', {
        source: source.name,
        julianDay: params.julianDay,
        body: params.body,
        requestedAccuracy: params.requestedAccuracy,
      });

      // Calculate using selected source
      const result = await this.calculateWithSource(params, source);

      // Cross-validate for critical calculations
      const shouldCrossValidate = this.shouldCrossValidate(params, source);
      if (shouldCrossValidate) {
        const validationResult = await this.crossValidateCalculation(params, source, result);
        result.crossValidated = true;
        result.validationDiscrepancy = validationResult.discrepancy;
      }

      result.calculationTime = Date.now() - startTime;
      
      logger.debug('Calculation completed', {
        source: result.ephemerisSource,
        calculationTime: result.calculationTime,
        accuracy: result.accuracy,
        crossValidated: result.crossValidated,
      });

      return result;

    } catch (error) {
      logger.error('Calculation failed:', { params, error: error.message });
      throw error;
    }
  }

  private async calculateWithSource(
    params: CalculationParams, 
    source: EphemerisSource
  ): Promise<EnhancedPosition> {
    
    if (source.type === 'swiss') {
      return this.calculateWithSwiss(params, source);
    } else if (source.type === 'jpl') {
      return this.calculateWithJPL(params, source);
    } else {
      throw new Error(`Unsupported ephemeris type: ${source.type}`);
    }
  }

  private calculateWithSwiss(
    params: CalculationParams, 
    source: EphemerisSource
  ): EnhancedPosition {
    const flags = params.flags || (swisseph.SEFLG_SWIEPH | swisseph.SEFLG_SPEED);

    const result = swisseph.swe_calc_ut(params.julianDay, params.body, flags);

    if (result.error) {
      throw new Error(`Swiss Ephemeris calculation error: ${result.error}`);
    }

    return {
      longitude: result.longitude,
      latitude: result.latitude,
      distance: result.distance,
      speed: result.longitudeSpeed,
      calculationTime: 0, // Will be set by caller
      accuracy: source.accuracy,
      ephemerisSource: source.name,
      sourceType: 'swiss',
    };
  }

  private async calculateWithJPL(
    params: CalculationParams, 
    source: EphemerisSource
  ): Promise<EnhancedPosition> {
    // TODO: Implement JPL SPICE integration
    // For now, fallback to Swiss with a note
    
    logger.warn('JPL calculation requested but not yet implemented, using Swiss fallback');
    
    const swissSource = this.ephemerisManager.getAvailableSources()
      .find(s => s.type === 'swiss');
    
    if (!swissSource) {
      throw new Error('JPL calculation not implemented and no Swiss fallback available');
    }

    const result = this.calculateWithSwiss(params, swissSource);
    result.ephemerisSource = `${source.name} (Swiss fallback)`;
    result.sourceType = 'swiss';
    
    return result;
  }

  private shouldCrossValidate(params: CalculationParams, source: EphemerisSource): boolean {
    // Cross-validate for high-accuracy requests or critical dates
    const isHighAccuracyRequest = params.requestedAccuracy && params.requestedAccuracy < 1.0;
    const isModernDate = params.julianDay >= 2305424.5 && params.julianDay <= 2816787.5;
    const hasMultipleSources = this.ephemerisManager.getAvailableSources().length > 1;
    
    return hasMultipleSources && (isHighAccuracyRequest || isModernDate);
  }

  private async crossValidateCalculation(
    params: CalculationParams,
    primarySource: EphemerisSource,
    primaryResult: EnhancedPosition
  ): Promise<{ discrepancy: number; secondarySource: string }> {
    
    try {
      // Find alternative source for validation
      const alternativeSources = this.ephemerisManager.getAvailableSources()
        .filter(s => s.name !== primarySource.name)
        .filter(s => 
          params.julianDay >= s.dateRangeStart && 
          params.julianDay <= s.dateRangeEnd
        );

      if (alternativeSources.length === 0) {
        return { discrepancy: 0, secondarySource: 'none available' };
      }

      // Use highest priority alternative source
      const secondarySource = alternativeSources.sort((a, b) => b.priority - a.priority)[0];
      const secondaryResult = await this.calculateWithSource(params, secondarySource);

      // Calculate discrepancy in arcseconds
      const longitudeDiff = Math.abs(primaryResult.longitude - secondaryResult.longitude) * 3600;
      const latitudeDiff = Math.abs(primaryResult.latitude - secondaryResult.latitude) * 3600;
      const discrepancy = Math.max(longitudeDiff, latitudeDiff);

      logger.debug('Cross-validation completed', {
        primarySource: primarySource.name,
        secondarySource: secondarySource.name,
        discrepancy: discrepancy.toFixed(3),
      });

      return { discrepancy, secondarySource: secondarySource.name };

    } catch (error) {
      logger.warn('Cross-validation failed:', error);
      return { discrepancy: -1, secondarySource: 'validation failed' };
    }
  }

  getEngineInfo() {
    return {
      version: swisseph.swe_version(),
      initialized: this.isInitialized,
      ephemerisSources: this.ephemerisManager.getSourceInfo(),
    };
  }
}

// Singleton for easy access
let engineInstance: EnhancedSwissEngine | null = null;

export function getEnhancedSwissEngine(): EnhancedSwissEngine {
  if (!engineInstance) {
    engineInstance = new EnhancedSwissEngine();
  }
  return engineInstance;
}
```

#### **3. Cross-Validation Framework**
```typescript
// src/core/cross-validator.ts
interface ValidationTest {
  name: string;
  julianDay: number;
  body: number;
  expectedAccuracy: number; // arcseconds
  referenceSources: string[];
}

const GOLDEN_VALIDATION_TESTS: ValidationTest[] = [
  {
    name: 'J2000.0 Sun Position',
    julianDay: 2451545.0,
    body: 0,
    expectedAccuracy: 0.1, // Very high accuracy expected
    referenceSources: ['JPL DE440', 'Swiss SE1'],
  },
  {
    name: 'J2000.0 Moon Position', 
    julianDay: 2451545.0,
    body: 1,
    expectedAccuracy: 1.0, // Moon is more complex
    referenceSources: ['JPL DE440', 'Swiss SE1'],
  },
  {
    name: 'Modern Mars Position',
    julianDay: 2460000.0, // ~2023
    body: 4,
    expectedAccuracy: 0.5,
    referenceSources: ['JPL DE440', 'JPL DE441'],
  },
  {
    name: 'Historical Venus (1600 CE)',
    julianDay: 2305448.5,
    body: 3,
    expectedAccuracy: 2.0, // Less accuracy for historical
    referenceSources: ['JPL DE441', 'Swiss SE1'],
  },
];

export class CrossValidator {
  constructor(private engine: EnhancedSwissEngine) {}

  async runValidationSuite(): Promise<ValidationResult[]> {
    const results: ValidationResult[] = [];

    for (const test of GOLDEN_VALIDATION_TESTS) {
      try {
        const validationResult = await this.runSingleValidation(test);
        results.push(validationResult);
        
        const status = validationResult.passed ? '✅ PASSED' : '❌ FAILED';
        logger.info(`Validation ${status}: ${test.name}`, {
          discrepancy: validationResult.discrepancyArcsec?.toFixed(3),
          tolerance: test.expectedAccuracy,
        });

      } catch (error) {
        results.push({
          testName: test.name,
          passed: false,
          error: error.message,
        });
        
        logger.error(`Validation ERROR: ${test.name}`, error);
      }
    }

    return results;
  }

  private async runSingleValidation(test: ValidationTest): Promise<ValidationResult> {
    // Calculate with multiple sources and compare
    const calculations: EnhancedPosition[] = [];

    for (const sourceName of test.referenceSources) {
      try {
        const result = await this.engine.calculatePosition({
          julianDay: test.julianDay,
          body: test.body,
          preferredSource: sourceName,
        });
        calculations.push(result);
      } catch (error) {
        logger.warn(`Could not calculate with ${sourceName}:`, error);
      }
    }

    if (calculations.length < 2) {
      throw new Error(`Insufficient sources for validation (need 2+, got ${calculations.length})`);
    }

    // Compare all pairs and find maximum discrepancy
    let maxDiscrepancy = 0;
    let comparison = '';

    for (let i = 0; i < calculations.length; i++) {
      for (let j = i + 1; j < calculations.length; j++) {
        const calc1 = calculations[i];
        const calc2 = calculations[j];

        const lonDiff = Math.abs(calc1.longitude - calc2.longitude) * 3600;
        const latDiff = Math.abs(calc1.latitude - calc2.latitude) * 3600;
        const discrepancy = Math.max(lonDiff, latDiff);

        if (discrepancy > maxDiscrepancy) {
          maxDiscrepancy = discrepancy;
          comparison = `${calc1.ephemerisSource} vs ${calc2.ephemerisSource}`;
        }
      }
    }

    const passed = maxDiscrepancy <= test.expectedAccuracy;

    return {
      testName: test.name,
      passed,
      discrepancyArcsec: maxDiscrepancy,
      toleranceArcsec: test.expectedAccuracy,
      comparison,
      sourceCount: calculations.length,
      calculations,
    };
  }
}
```

### **Step 1 Success Criteria:**
- [ ] Swiss .se1 files load and calculate correctly
- [ ] JPL file existence validated (calculation pending SPICE integration)
- [ ] Auto-source selection works for different date ranges
- [ ] Cross-validation shows discrepancy < 1 arcsecond between sources
- [ ] All golden validation tests pass

## 🚀 **Step 2: Intelligent Caching with Source Awareness**

### **Enhanced Cache with Source Differentiation**
```typescript
// src/cache/ephemeris-aware-cache.ts
export class EphemerisAwareCache {
  private redis: Redis;

  private getCacheKey(
    julianDay: number, 
    body: number, 
    ephemerisSource: string,
    accuracy: number
  ): string {
    const roundedJD = Math.round(julianDay * 1000000) / 1000000;
    const accuracyTier = this.getAccuracyTier(accuracy);
    return `calc:${roundedJD}:${body}:${ephemerisSource}:${accuracyTier}`;
  }

  private getAccuracyTier(accuracy: number): string {
    if (accuracy <= 0.001) return 'ultra';
    if (accuracy <= 0.1) return 'high';
    return 'standard';
  }

  private getTTL(julianDay: number, ephemerisSource: string): number {
    const now = Date.now();
    const calculationDate = (julianDay - 2440587.5) * 86400000;
    const daysDiff = Math.abs((now - calculationDate) / (1000 * 60 * 60 * 24));
    
    // JPL sources have longer cache times due to higher computation cost
    const isJPL = ephemerisSource.includes('JPL');
    const multiplier = isJPL ? 2 : 1;
    
    if (daysDiff > 365) return 604800 * multiplier; // 1-2 weeks for historical
    if (daysDiff > 30) return 86400 * multiplier;   // 1-2 days for recent
    return 3600 * multiplier;                       // 1-2 hours for current
  }

  async get(
    julianDay: number, 
    body: number, 
    ephemerisSource: string,
    accuracy: number
  ): Promise<EnhancedPosition | null> {
    try {
      const key = this.getCacheKey(julianDay, body, ephemerisSource, accuracy);
      const cached = await this.redis.get(key);
      return cached ? JSON.parse(cached) : null;
    } catch (error) {
      logger.warn('Cache get failed:', error);
      return null;
    }
  }

  async set(
    julianDay: number, 
    body: number, 
    result: EnhancedPosition
  ): Promise<void> {
    try {
      const key = this.getCacheKey(
        julianDay, 
        body, 
        result.ephemerisSource, 
        result.accuracy
      );
      const ttl = this.getTTL(julianDay, result.ephemerisSource);
      await this.redis.setex(key, ttl, JSON.stringify(result));
    } catch (error) {
      logger.warn('Cache set failed:', error);
    }
  }
}
```

### **Step 2 Success Criteria:**
- [ ] Cache hit rate > 80% for repeated calculations
- [ ] Different ephemeris sources cached separately
- [ ] JPL calculations get longer cache TTL (higher computation cost)
- [ ] Cache key includes accuracy tier to prevent incorrect hits

## 🔐 **Step 3: Security Foundation** 
*(Same as previous plan - no changes needed)*

## 🌐 **Step 4: Production API with Intelligent Switching**

### **Enhanced Calculate Endpoint**
```typescript
// src/api/enhanced-calculate-endpoint.ts
fastify.post('/api/v1/calculate', {
  schema: {
    body: z.object({
      julianDay: z.number().min(1721425.5).max(5373484.5),
      body: z.union([
        z.enum(['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']),
        z.number().int().min(0).max(1000)
      ]),
      accuracy: z.enum(['standard', 'high', 'ultra']).default('standard'),
      ephemerisSource: z.enum(['auto', 'swiss', 'jpl-de440', 'jpl-de441']).default('auto'),
      crossValidate: z.boolean().default(false),
    }),
  },
}, async (request, reply) => {
  const startTime = Date.now();
  
  try {
    const { julianDay, body, accuracy, ephemerisSource, crossValidate } = request.body;
    const bodyId = typeof body === 'string' ? BODY_MAP[body] : body;
    
    // Convert accuracy level to arcseconds
    const accuracyMap = {
      standard: 1.0,
      high: 0.1,
      ultra: 0.001,
    };
    const requestedAccuracy = accuracyMap[accuracy];

    // Try cache first (with source and accuracy awareness)
    const engine = getEnhancedSwissEngine();
    const selectedSource = ephemerisSource === 'auto' 
      ? engine.ephemerisManager.selectOptimalSource(julianDay, requestedAccuracy)
      : ephemerisSource;

    const cached = await cache.get(julianDay, bodyId, selectedSource.name, requestedAccuracy);
    if (cached && !crossValidate) {
      return {
        success: true,
        data: cached,
        cached: true,
        metadata: {
          ephemerisSource: cached.ephemerisSource,
          autoSelected: ephemerisSource === 'auto',
          responseTime: Date.now() - startTime,
        },
      };
    }

    // Calculate with intelligent source selection
    const result = await engine.calculatePosition({
      julianDay,
      body: bodyId,
      requestedAccuracy,
      preferredSource: ephemerisSource === 'auto' ? undefined : ephemerisSource,
    });

    // Cache the result
    await cache.set(julianDay, bodyId, result);

    // Enhanced response with ephemeris metadata
    return {
      success: true,
      data: result,
      cached: false,
      metadata: {
        ephemerisSource: result.ephemerisSource,
        sourceType: result.sourceType,
        autoSelected: ephemerisSource === 'auto',
        crossValidated: result.crossValidated,
        validationDiscrepancy: result.validationDiscrepancy,
        availableSources: engine.ephemerisManager.getAvailableSources().map(s => s.name),
        responseTime: Date.now() - startTime,
      },
    };

  } catch (error) {
    logger.error('Enhanced calculation failed:', error);
    return reply.status(500).send({
      success: false,
      error: 'Calculation failed',
      message: error.message,
      responseTime: Date.now() - startTime,
    });
  }
});
```

### **Ephemeris Info Endpoint**
```typescript
// src/api/ephemeris-info-endpoint.ts
fastify.get('/api/v1/ephemeris/info', async (request, reply) => {
  const engine = getEnhancedSwissEngine();
  
  return {
    sources: engine.getEngineInfo().ephemerisSources,
    dateRanges: {
      'swiss-se1': '1 CE - 10000 CE',
      'jpl-de440': '1550 CE - 2650 CE (highest accuracy)',
      'jpl-de441': '1 CE - 10000 CE (extended range)',
    },
    autoSelection: {
      description: 'Automatic source selection based on date and accuracy requirements',
      rules: [
        'JPL DE440: 1550-2650 CE for highest accuracy',
        'JPL DE441: Extended dates with high accuracy', 
        'Swiss SE1: Default for speed and general accuracy',
      ],
    },
    accuracyLevels: {
      standard: '~1.0 arcsecond',
      high: '~0.1 arcsecond',
      ultra: '~0.001 arcsecond (milliarcsecond)',
    },
  };
});
```

### **Step 4 Success Criteria:**
- [ ] API automatically selects optimal ephemeris source
- [ ] Modern dates (1550-2650) use JPL DE440 by default
- [ ] Extended dates use JPL DE441 when available
- [ ] Swiss SE1 provides fast fallback
- [ ] Cross-validation available for critical calculations
- [ ] Response includes ephemeris metadata for transparency

## 📊 **Enhanced Success Metrics**

### **Accuracy Metrics by Source**
```typescript
interface EphemerisMetrics {
  swissSE1: {
    averageAccuracy: number;    // Target: < 1.0 arcsec
    calculationSpeed: number;   // Target: < 50ms
    dateRangeCoverage: string;  // 1 CE - 10000 CE
  };
  jplDE440: {
    averageAccuracy: number;    // Target: < 0.001 arcsec
    calculationSpeed: number;   // Target: < 200ms
    dateRangeCoverage: string;  // 1550 - 2650 CE
  };
  jplDE441: {
    averageAccuracy: number;    // Target: < 0.01 arcsec
    calculationSpeed: number;   // Target: < 300ms
    dateRangeCoverage: string;  // 1 CE - 10000 CE
  };
}
```

## 🎯 **Implementation Timeline**

### **Step 1: Multi-Ephemeris Core (Days 1-5)**
- **Day 1**: Ephemeris manager and source selection logic
- **Day 2**: Enhanced Swiss engine with auto-switching
- **Day 3**: Cross-validation framework
- **Day 4**: JPL file validation (SPICE integration starts)
- **Day 5**: Golden validation test suite

### **Step 2: Smart Caching (Days 6-8)**
- **Day 6**: Cache with ephemeris source awareness
- **Day 7**: TTL optimization by source type
- **Day 8**: Cache performance testing

### **Step 3: Security (Days 9-12)**
- **Day 9-12**: Same as previous security plan

### **Step 4: Production API (Days 13-15)**
- **Day 13**: Enhanced calculate endpoint
- **Day 14**: Ephemeris info and metadata endpoints
- **Day 15**: Integration testing and documentation

---

This enhanced foundation provides **intelligent ephemeris switching** that automatically optimizes for accuracy and performance based on date ranges, while maintaining the same anti-90/90 rule safeguards. The system will use the most appropriate data source for each calculation automatically.
