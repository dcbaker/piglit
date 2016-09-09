/* Tests that the OpenGL special variable gl_ViewportIndex can be set in a
 * vertex shader
 *
 * [config]
 * expect_result: pass
 * glsl_version: 4.10
 * require_extensions: GL_ARB_shader_viewport_layer_array
 * [end config]
 */

#version 410
#extension GL_ARB_shader_viewport_layer_array : require

void main()
{
    gl_ViewportIndex = 1;
}
