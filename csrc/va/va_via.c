#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <math.h>

#include "va.h"


/*
 * Our via type is whats used for the nice rounded drawing.
 *
 * Basically, it has the centroid, the radius, and (r_inside/r)**2
 *
 * This allows us to render efficiently by drawing a square with x, y in (-1..1),
 * and testing in the fragment shader whether x**2 + y**2 < 1 (for outer radius)
 * and x**2 + y**2 > r_inside_frac_sq
 */
struct inst_via{
	float x, y;
	float r, r_ins_frac_sq;
};

/*
 * Check-and-grow macro
 */
#define CHECK(n) { assert(va->stride == sizeof(struct inst_via)); vertex_array_check_grow(va, (n)); }

/*
 * Internal via array append
 * Presumes array has sufficient size
 */
static void _via_array_append(struct vertex_array * va, float x, float y, float r, float r_inside)
{
	assert(va->stride == sizeof(struct inst_via));

	struct inst_via* ptr = (struct inst_via *)va->data;

	ptr[va->index].x = x;
	ptr[va->index].y = y;
	ptr[va->index].r = r;
	ptr[va->index].r_ins_frac_sq = (r_inside / r) * (r_inside/r);
	va->index++;
	va->count = va->index;
}

/* 
 * Public export - append a single via to the VA
 */
void via_array_append(struct vertex_array * va, float x, float y, float r, float r_inside)
{
	CHECK(1);
	_via_array_append(va, x, y, r, r_inside);
}


/*
 * 
 * void via_array_project_extend(struct vertex_array * dest, struct vertex_array * src, struct matrix3x2 * a)
{
}*/
