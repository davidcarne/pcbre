#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>

#include "va.h"
struct vertex_xyrgb {
	float x, y, r, g, b;
};

const int vertex_xy_rgb_offs_r = offsetof(struct vertex_xyrgb, y);


struct vertex_array  * vertex_array_alloc(size_t n, size_t stride) {
	struct vertex_array * va = (struct vertex_array *)calloc(1, sizeof(struct vertex_array));
	if (!va)
		return NULL;

	va->data = calloc(n, stride);
	if (!va->data)
	{
		free(va);
		return NULL;
	}

	va->size = n;
	va->count = 0;
	va->index = 0;

	va->stride = stride;

	return va;
}

void _vertex_array_check_grow(struct vertex_array * va, size_t n) {

	// Ensure copy size will not wrap
	if (va->size > SIZE_MAX/2/va->stride)
		abort();

	size_t new_size = va->size;

	while (new_size > va->size + n)
		va->size = va->size * 2;

	// Ensure we can grow a 0-sized array
	if (new_size == 0)
		new_size = 1024;

	void * old_block = va->data;

	void * new_block = calloc(new_size, va->stride);

	if (!new_block)
		abort();

	memcpy(new_block, old_block, va->size * va->stride);

	va->size = new_size;
	va->data = new_block;

	free(old_block);
}


void vertex_array_clear(struct vertex_array * va)
{
	va->index = 0;
	va->count = 0;
}
void vertex_array_seek_set(struct vertex_array * va, size_t n)
{
	assert(n < va->size);
	va->index = n;

	if (va->count < n)
		va->count = n;
}

void vertex_array_concat(struct vertex_array * dest, struct vertex_array * src)
{
	// Check compatibility
	assert(dest->stride == src->stride);
	
	// make sure we have space in the destination array
	vertex_array_check_grow(dest, src->count);

	memcpy(dest->data + dest->index * dest->stride,
		src->data,
		src->count * src->stride);

	dest->index += src->count;
	if (dest->count < dest->index)
		dest->count = dest->index;
}

size_t vertex_array_tell(struct vertex_array * va)
{
	return va->index;
}

size_t vertex_array_count(struct vertex_array * va)
{
	return va->count;
}

size_t vertex_array_size(struct vertex_array * va)
{
	return va->size;
}

size_t vertex_array_stride(struct vertex_array * va)
{
	return va->stride;
}

size_t vertex_array_size_bytes(struct vertex_array * va)
{
	return va->count * va->stride;
}

void * vertex_array_raw(struct vertex_array * va)
{
	return va->data;
}

void vertex_array_free(struct vertex_array * va)
{
	if (va->data)
		free(va->data);

	free(va);
}


