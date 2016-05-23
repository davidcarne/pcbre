#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <math.h>

#include "va.h"


struct inst_tex {
	float x, y;
	float tx, ty;
};

#define CHECK(n) { assert(va->stride == sizeof(struct inst_tex)); vertex_array_check_grow(va, (n)); }

static void _tex_array_append(struct vertex_array * va, float x, float y, float tx, float ty)
{
	assert(va->stride == sizeof(struct inst_tex));

	struct inst_tex* ptr = (struct inst_tex *)va->data;

	ptr[va->index].x = x;
	ptr[va->index].y = y;
	ptr[va->index].tx = tx;
	ptr[va->index].ty = ty;

	va->index++;
	va->count = va->index;
}

void tex_array_append(struct vertex_array * va, float x, float y, float tx, float ty)
{
	CHECK(1);
	_tex_array_append(va, x, y, tx, ty);
}

/*
 *   Element layout
 *
 *   c0 c1 c2
 *   c3 c4 c5
 */
void tex_extend_project(struct vertex_array * dest, struct vertex_array * src, 
	float c0, float c1, float c2, float c3, float c4, float c5)
{
	assert(dest->stride == sizeof(struct inst_tex));
	assert(src->stride == sizeof(struct inst_tex));
	vertex_array_check_grow(dest, src->count);

	struct inst_tex * src_p = (struct inst_tex *)src->data;
	struct inst_tex * dest_p = (struct inst_tex *)dest->data + dest->index;

	for (size_t i=0; i < src->count; i++)
	{
		dest_p[i].x = c0 * src_p[i].x + c1 * src_p[i].y + c2;
		dest_p[i].y = c3 * src_p[i].x + c4 * src_p[i].y + c5;
		dest_p[i].tx = src_p[i].tx;
		dest_p[i].ty = src_p[i].ty;
	}

	dest->index += src->count;
	if (dest->count < dest->index)
		dest->count = dest->index;
}

