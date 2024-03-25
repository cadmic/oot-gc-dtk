#include "dolphin/types.h"
#include "macros.h"

s32 xlTextCopy(char* acTextTarget, char* szTextSource) {
    s32 iCharacter;

    for (iCharacter = 0; szTextSource[iCharacter] != '\0'; iCharacter++) {
        acTextTarget[iCharacter] = szTextSource[iCharacter];
    }

    acTextTarget[iCharacter] = '\0';
    return iCharacter;
}

s32 xlTextMatch(char* acText1, char* acText2) {
    s32 iCharacter;
    s32 nCharacter1;
    s32 nCharacter2;

    nCharacter1 = 0;
    while (acText1[nCharacter1] != '\0') {
        nCharacter1++;
    }

    nCharacter2 = 0;
    while (acText2[nCharacter2] != '\0') {
        nCharacter2++;
    }

    if (nCharacter1 == nCharacter2) {
        s32 upper1;
        s32 upper2;

        iCharacter = nCharacter1;
        while (iCharacter > 0) {
            s32 nCharacter1 = *acText1;
            s32 nCharacter2 = *acText2;

            upper1 = nCharacter1;
            if ((nCharacter1 >= 'a') && (upper1 <= 'z')) {
                upper1 -= ' ';
            }

            upper2 = nCharacter2;
            if ((nCharacter2 >= 'a') && (nCharacter2 <= 'z')) {
                upper2 -= ' ';
            }

            if (upper1 != upper2) {
                return 0;
            }

            *acText2++;
            *acText1++;
            iCharacter--;
        }
        return 1;
    }
    return 0;
}
