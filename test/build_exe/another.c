#include "another.h"
#include <stdio.h>

void another_foo() {
  Foo myfoo = {.foo = 42};
  puts("another foo");
  yet_another_foo(myfoo);
}
