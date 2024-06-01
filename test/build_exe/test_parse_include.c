#include "another.h"
#include "other.h"
#include <stdio.h>

#define bar 42

int main(void) {
#if __GNUC__ == 14
  printf("%b", bar);
#else
  printf("%x", bar);
#endif
  foo();
  another_foo();
  return 0;
}
