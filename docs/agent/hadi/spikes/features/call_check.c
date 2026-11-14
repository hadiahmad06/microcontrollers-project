// [AI-GENERATED: Claude Code]
#include "features.h"

static int16_t window_buf[FEAT_WINDOW_LEN][FEAT_AXES]; /* plain, non-const capture buffer */
static int16_t feat_buf[FEAT_COUNT];

/**
 * Compile-only check: calling features_extract with a plain int16_t[150][3]
 * buffer must produce zero warnings (xc16-gcc 2.10, -O1 and -O2).
 *
 * @param void No arguments.
 * @return     First feature, so the call is not optimised away.
 */
int16_t call_check(void)
{
    features_extract(window_buf, feat_buf);
    return feat_buf[0];
}
// [END AI-GENERATED]
