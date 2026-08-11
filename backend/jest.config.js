/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  transform: {
    // tsconfig's Node16 moduleResolution (needed for real ESM/CJS interop
    // elsewhere) requires isolatedModules under ts-jest, or it just warns
    // on every run without actually failing anything.
    '^.+\\.tsx?$': ['ts-jest', { isolatedModules: true }],
  },
  roots: ['<rootDir>/tests'],
  testMatch: ['**/*.test.ts'],
  // mongodb-memory-server downloads/starts a real mongod binary the first
  // time it runs in an environment - slower than a typical unit test.
  testTimeout: 60000,
};
