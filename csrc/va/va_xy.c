#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <math.h>

#include "va.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define HALF_PI (M_PI/2)

struct vertex_xy {
	float x, y;
};

#define CHECK(n) { assert(va->stride == sizeof(struct vertex_xy)); vertex_array_check_grow(va, (n)); }
//#define CHECK(n)


static void _vertex_xy_array_append(struct vertex_array * va, float x, float y)
{
	assert(va->stride == sizeof(struct vertex_xy));

	struct vertex_xy * ptr = (struct vertex_xy *)va->data;

	ptr[va->index].x = x;
	ptr[va->index].y = y;
	va->index++;
	va->count = va->index;
}

void vertex_xy_array_append(struct vertex_array * va, float x, float y)
{
	CHECK(1);
	_vertex_xy_array_append(va, x, y);
}

void vertex_xy_array_bench(struct vertex_array * va, size_t count)
{
	for(size_t i=0; i<count; i++)
		vertex_xy_array_append(va, 1.2, 1.2);
}

static void _vertex_xy_array_line(struct vertex_array * va, float x0, float y0, float x1, float y1)
{
	vertex_xy_array_append(va, x0, y0);
	vertex_xy_array_append(va, x1, y1);
}

void vertex_xy_array_line(struct vertex_array * va, float x0, float y0, float x1, float y1)
{
	CHECK(2);
	_vertex_xy_array_line(va, x0, y0, x1, y1);
}

void vertex_xy_array_aligned_box(struct vertex_array * va, float cx, float cy, float w, float h)
{
	CHECK(8);

	float x_1 = cx - w/2;
	float x_2 = cx + w/2;

	float y_1 = cy - h/2;
	float y_2 = cy + h/2;

	_vertex_xy_array_line(va, x_1, y_1, x_2, y_1);
	_vertex_xy_array_line(va, x_2, y_1, x_2, y_2);
	_vertex_xy_array_line(va, x_2, y_2, x_1, y_2);
	_vertex_xy_array_line(va, x_1, y_2, x_1, y_1);
}

void vertex_xy_array_box(struct vertex_array * va, float cx, float cy, float w, float h, float theta)
{
	CHECK(8);

	/* Rotation matrix coefficients
	 *    2 _
	 *    /  -_  1
	 *   /    /
	 *-1/_   / theta
	 *    -_/__
	 *     -2
	 */

	float cos_t = cosf(theta);
	float sin_t = sinf(theta);

	
	float x_a =  cos_t * w/2;
	float y_a =  sin_t * w/2;

	float x_b = -sin_t * h/2;
	float y_b =  cos_t * h/2;

	float x_1 = x_a - x_b;
	float y_1 = y_a - y_b;
	
	float x_2 = x_a + x_b;
	float y_2 = y_a + y_b;

	_vertex_xy_array_line(va, cx - x_2, cy - y_2, cx + x_1, cy + y_1);
	_vertex_xy_array_line(va, cx + x_1, cy + y_1, cx + x_2, cy + y_2);
	_vertex_xy_array_line(va, cx + x_2, cy + y_2, cx - x_1, cy - y_1);
	_vertex_xy_array_line(va, cx - x_1, cy - y_1, cx - x_2, cy - y_2);
	
}

void vertex_xy_array_roundrect(struct vertex_array * va, float cx, float cy, float w, float h, float theta, float corner_r, size_t n_corner_step)
{

	// 2 verticies per line, 4 corners..
	size_t n_verts = (n_corner_step + 1) * 2 * 4 + 8;

	CHECK(n_verts);

	/* Rotation matrix coefficients
	 *    2 _
	 *    /  -_  1
	 *   /    /
	 *-1/_   / theta
	 *    -_/__
	 *     -2
	 *
	 */

	float cos_t = cosf(theta);
	float sin_t = sinf(theta);

	
	// horizontal ("A") axis vector
	float x_a   =  cos_t * w/2;
	float y_a   =  sin_t * w/2;
	float x_a_c =  cos_t * (w/2 - corner_r);
	float y_a_c =  sin_t * (w/2 - corner_r);

	// vertical ("B") axis vector
	float x_b = -sin_t * h/2;
	float y_b =  cos_t * h/2;
	float x_b_c = -sin_t * (h/2 - corner_r);
	float y_b_c =  cos_t * (h/2 - corner_r);

	// Bottom
	_vertex_xy_array_line(va, cx - x_a_c - x_b  , cy - y_a_c - y_b  , cx + x_a_c - x_b  , cy + y_a_c - y_b  );

	// Right
	_vertex_xy_array_line(va, cx + x_a   - x_b_c, cy + y_a   - y_b_c, cx + x_a   + x_b_c, cy + y_a   + y_b_c);

	// Top
	_vertex_xy_array_line(va, cx + x_a_c + x_b  , cy + y_a_c + y_b  , cx - x_a_c + x_b  , cy - y_a_c + y_b  );

	// Left
	_vertex_xy_array_line(va, cx - x_a   + x_b_c, cy - y_a   + y_b_c, cx - x_a   - x_b_c, cy - y_a   - y_b_c);


	// Corners, starting at top-right, running clockwise
	for (size_t corner=0; corner <4; corner++)
	{
		float x,y;

		// Coordinates of center-radius of corner
		switch (corner)
		{
			case 0:
				x = cx + x_a_c + x_b_c;
				y = cy + y_a_c + y_b_c;
				break;
			case 1:
				x = cx - x_a_c + x_b_c;
				y = cy - y_a_c + y_b_c;
				break;
			case 2:
				x = cx - x_a_c - x_b_c;
				y = cy - y_a_c - y_b_c;
				break;
			case 3:
				x = cx + x_a_c - x_b_c;
				y = cy + y_a_c - y_b_c;
				break;
		}

		// Step around corner
		for (size_t i=0; i<n_corner_step + 1; i++)
		{
			float c_t = ((float)i / n_corner_step + corner)* HALF_PI + theta;

			float cos_2 = cosf(c_t) * corner_r;
			float sin_2 = sinf(c_t) * corner_r;


			_vertex_xy_array_append(va, x + cos_2, y + sin_2);
			if (i != 0 && i != n_corner_step)
				_vertex_xy_array_append(va, x + cos_2, y + sin_2);

		}
	}
}

void vertex_xy_array_circle(struct vertex_array * va, float cx, float cy, float r, size_t n_step)
{
	CHECK((n_step + 1) * 2);
	
	for (size_t i=0; i<n_step + 1; i++)
	{
		float theta = (float)i / n_step * M_PI * 2;

		float x = cx + cosf(theta) * r;
		float y = cy + sinf(theta) * r;

		_vertex_xy_array_append(va, x, y);
		if (i != 0 && i != n_step)
			_vertex_xy_array_append(va, x, y);

	}
}

/*
 * Arc always drawn counter-clockwise
 */
void vertex_xy_array_arc(struct vertex_array * va, float cx, float cy, float r, float theta0, float theta1, size_t n_step)
{
	CHECK((n_step + 1) * 2);

	float delta_theta = theta1 - theta0;

	/* Normalize */
	if (delta_theta < 0)
		delta_theta += M_PI * 2;

	
	for (size_t i=0; i<n_step + 1; i++)
	{
		float theta = (float)i / n_step * delta_theta + theta0;

		float x = cx + cosf(theta) * r;
		float y = cy + sinf(theta) * r;

		_vertex_xy_array_append(va, x, y);
		if (i != 0 && i != n_step)
			_vertex_xy_array_append(va, x, y);

	}
}

