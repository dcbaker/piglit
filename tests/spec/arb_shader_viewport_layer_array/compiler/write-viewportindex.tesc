/* gl_ViewportIndex should be undefined in a Teselation Control Shader.
 *
 * [config]
 * expect_result: fail
 * glsl_version: 4.10
 * require_extensions: GL_ARB_shader_viewport_layer_array
 * [end config]
 */

#version 410

void main()
{
    gl_ViewportIndex = 1;
}
