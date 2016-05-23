#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <math.h>

#include "va.h"


struct inst_trace {
	float ax, ay;
	float bx, by;
	float t;
};

#define CHECK(n) { assert(va->stride == sizeof(struct inst_trace)); vertex_array_check_grow(va, (n)); }

static void _trace_array_append(struct vertex_array * va, float ax, float ay, float bx, float by, float t)
{
	assert(va->stride == sizeof(struct inst_trace));

	struct inst_trace* ptr = (struct inst_trace *)va->data;

	ptr[va->index].ax = ax;
	ptr[va->index].ay = ay;
	ptr[va->index].bx = bx;
	ptr[va->index].by = by;
	ptr[va->index].t = t;
	va->index++;
	va->count = va->index;
}

void trace_array_append(struct vertex_array * va, float ax, float ay, float bx, float by, float t)
{
	CHECK(1);
	_trace_array_append(va, ax, ay, bx, by, t);
}

