
#version 150

uniform usampler2D layer_info;
uniform sampler1D color_tab;

// rgb are per-layer color
// a is composite stack alpha
uniform vec4 layer_color;

in vec2 texpos_v;
out vec4 final_color;

void main() {
    // Basic Alpha blending (for now)
    // TODO - rise selections


    float alpha = texture(layer_info, texpos_v).r/255.0;// * layer_color.a/255.0;
    uint type = texture(layer_info, texpos_v).g;


    final_color.a = alpha * layer_color.a/255.0;

    if (type == 0u) {
        final_color.rgb = layer_color.rgb * alpha;
    } else {
        final_color.rgb = texelFetch(color_tab, int(type), 0).rgb * alpha;
    }
}