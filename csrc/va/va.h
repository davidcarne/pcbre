#ifndef _VA_H_
#define _VA_H_

#include <stddef.h>
#include <stdlib.h>

struct vertex_array {
	size_t size;
	size_t count;
	size_t index;
	size_t stride;
	void * data;
};


void _vertex_array_check_grow(struct vertex_array * va, size_t n);

/* hoist the size check into the caller */
static inline void vertex_array_check_grow(struct vertex_array * va, size_t n)
{
	
	// If we would wrap, abort
	if (va->size > SIZE_MAX - n)
		abort();

	// + n won't wrap, therefore addition is safe
	if (va->index + n <= va->size)
		return;

	_vertex_array_check_grow(va, n);
}

struct matrix3x2 {
	/*  c_0_0  c_0_1  c_0_2
	 *  c_1_0  c_1_1  c_1_2
	 */
	float c_0_0, c_0_1, c_0_2, c_1_0, c_1_1, c_1_2;
};

#endif

