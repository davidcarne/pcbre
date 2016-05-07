#version 150

uniform uvec4 layer_info;

out uvec4 frag_info;

void main(void)
{
    frag_info.rg = layer_info.rg;
}