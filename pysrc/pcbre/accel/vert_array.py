from cffi import FFI

ffi = FFI()

ffi.cdef("""
struct vertex_array;
struct vertex_array  * vertex_array_alloc(size_t n, size_t stride);
void vertex_array_seek_set(struct vertex_array * va, size_t n);
size_t vertex_array_tell(struct vertex_array * va);
size_t vertex_array_count(struct vertex_array * va);
size_t vertex_array_size(struct vertex_array * va);
size_t vertex_array_clear(struct vertex_array * va);
size_t vertex_array_size_bytes(struct vertex_array * va);
void vertex_array_free(struct vertex_array * va);
void * vertex_array_raw(struct vertex_array * va);
void vertex_array_concat(struct vertex_array * dest, struct vertex_array * src);

void vertex_xy_array_append(struct vertex_array * va, float x, float y);
void vertex_xy_array_bench(struct vertex_array * va, size_t count);
void vertex_xy_array_line(struct vertex_array * va, float x0, float y0, float x1, float y1);
void vertex_xy_array_box(struct vertex_array * va, float cx, float cy, float w, float h, float theta);
void vertex_xy_array_aligned_box(struct vertex_array * va, float cx, float cy, float w, float h);
void vertex_xy_array_roundrect(struct vertex_array * va, float cx, float cy, float w, float h, float theta,
    float corner_r, size_t n_corner_step);


void vertex_xy_array_circle(struct vertex_array * va, float cx, float cy, float r, size_t n_step);
void vertex_xy_array_arc(struct vertex_array * va, float cx, float cy, float r, float theta0, float theta1,
    size_t n_step);

void trace_array_append(struct vertex_array * va, float ax, float ay, float bx, float by, float t);

void via_array_append(struct vertex_array * va, float x, float y, float r, float r_inside);

void tex_array_append(struct vertex_array * va, float x, float y, float tx, float ty);
void tex_extend_project(struct vertex_array * dest, struct vertex_array * src,
	float c0, float c1, float c2, float c3, float c4, float c5);


""")


from .find_so import find_so
lib = ffi.dlopen(find_so("_va"))

class VA:
    def __init__(self, size, stride):
        self._va = lib.vertex_array_alloc(size, stride)

    def seek(self, index):
        lib.vertex_array_seek_set(self._va, index)

    def tell(self):
        return lib.vertex_array_tell(self._va)

    def count(self):
        return lib.vertex_array_count(self._va)

    def clear(self):
        lib.vertex_array_clear(self._va)

    def size(self):
        return lib.vertex_array_size(self._va)

    def raw(self):
        buf = lib.vertex_array_raw(self._va)
        return buf

    def size_bytes(self):
        return lib.vertex_array_size_bytes(self._va)

    def buffer(self):
        return ffi.buffer(self.raw(), self.size_bytes())

    def extend(self, va):
        return lib.vertex_array_concat(self._va, va._va)

    def __del__(self):
        if self._va is not None:
            lib.vertex_array_free(self._va)
            self._va = None

class VA_xy(VA):
    def __init__(self, size):
        super(VA_xy, self).__init__(size, 8)


    def add_vertex(self, x0, y0):
        lib.vertex_xy_array_append(self._va, x0, y0)

    def add_line(self, x0, y0, x1, y1):
        lib.vertex_xy_array_line(self._va, x0, y0, x1, y1)

    def add_box(self, cx, cy, w, h, theta):
        lib.vertex_xy_array_box(self._va, cx, cy, w, h, theta)

    def add_box_round(self, cx, cy, w, h, theta, r, n_steps=4):
        lib.vertex_xy_array_roundrect(self._va, cx, cy, w, h, theta, r, n_steps)

    def add_aligned_box(self, cx, cy, w, h):
        lib.vertex_xy_array_aligned_box(self._va, cx, cy, w, h)

    def add_circle(self, cx, cy, r, n_steps=32):
        lib.vertex_xy_array_circle(self._va, cx, cy, r, n_steps)

    def add_arc(self, cx, cy, r, theta0, theta1, n_steps=4):
        """
        Draw a CCW arc starting at theta0 through theta1
        """
        lib.vertex_xy_array_arc(self._va, cx, cy, r, theta0, theta1, n_steps)


class VA_thickline(VA):
    def __init__(self, size):
        super(VA_thickline, self).__init__(size, 20)

    def add_thickline(self, x0, y0, x1, y1, t):
        lib.trace_array_append(self._va, x0, y0, x1, y1, t)

    # Convenience function for adding a trace to the thickline draw set
    def add_trace(self, t):
        lib.trace_array_append(self._va, t.p0.x, t.p0.y, t.p1.x, t.p1.y, t.thickness/2)

class VA_via(VA):
    def __init__(self, size):
        super(VA_via, self).__init__(size, 16)

    def add_donut(self, x, y, r, r_inside=0):
        lib.via_array_append(self._va, x, y, r, r_inside)

    def add_via(self, via):
        lib.via_array_append(self._va, via.pt.x, via.pt.y, via.r, 0)

class VA_tex(VA):
    def __init__(self, size):
        super(VA_tex, self).__init__(size, 16)

    def add_tex(self, x, y, tx, ty):
        lib.tex_array_append(self._va, x, y, tx, ty)

    def extend(self, va):
        return lib.vertex_array_concat(self._va, va._va)

    def extend_project(self, mat, src):
        return lib.tex_extend_project(self._va, src._va,
                mat[0][0], mat[0][1], mat[0][2], mat[1][0], mat[1][1], mat[1][2])