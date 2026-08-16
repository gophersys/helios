// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Version Definitions
 */

#ifndef ICLE_VERSION_H_
#define ICLE_VERSION_H_

#define ICLE_VERSION_MAJOR 1
#define ICLE_VERSION_MINOR 0
#define ICLE_VERSION_PATCH 0

#define ICLE_VERSION_STRING "1.0.0"
#define ICLE_VERSION_CODE ((ICLE_VERSION_MAJOR << 16) | \
			   (ICLE_VERSION_MINOR << 8) | \
			   ICLE_VERSION_PATCH)

#define ICLE_BUILD_DATE __DATE__
#define ICLE_BUILD_TIME __TIME__

#endif /* ICLE_VERSION_H_ */
