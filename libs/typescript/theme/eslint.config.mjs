// libs/typescript/theme/eslint.config.mjs — thin re-export of the shared strict flat config.
// The rule set lives in ONE home (../eslint.config.base.mjs); this file exists only so eslint
// resolves a config from the lib root and the projectService anchors at this lib's tsconfig.
import base from '../eslint.config.base.mjs';

export default base;
