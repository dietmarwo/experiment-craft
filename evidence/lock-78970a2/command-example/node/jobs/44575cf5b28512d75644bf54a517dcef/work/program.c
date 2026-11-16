#include <stdio.h>
int main(void) { FILE *f=fopen("answer.bin","wb"); unsigned char b[]={0,42,255}; if(!f)return 1; size_t n=fwrite(b,1,3,f); return fclose(f) || n!=3; }
