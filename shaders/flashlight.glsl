#ifdef VERTEX
attribute vec4 pos;
void main() {
    gl_Position = vec4(pos.xy, 0.0, 1.0);
}
#endif

#ifdef FRAGMENT
#ifdef GL_ES
precision highp float;
#endif

// Parameters for all agents are packed into textures. Each texel holds
// information for a single agent so that multiple agents can be processed in a
// single pass. ``agent0`` stores ``origin.x``, ``origin.y``, ``base_ang`` and
// ``fov_half``. ``agent1`` stores ``cone_len`` in the ``r`` component.
uniform sampler2D agent0;
uniform sampler2D agent1;
uniform float agent_count;
uniform float ray_steps;

uniform sampler2D colliders;
uniform int collider_count;

vec4 get_rect(int idx){
    float u = (float(idx) + 0.5) / float(collider_count);
    return texture2D(colliders, vec2(u, 0.5));
}

bool intersect_rect(vec2 o, vec2 d, vec4 rect, float cone_len, out float tHit){
    vec2 inv = 1.0 / d;
    vec2 t1 = (rect.xy - o) * inv;
    vec2 t2 = (rect.xy + rect.zw - o) * inv;
    vec2 tmin = min(t1, t2);
    vec2 tmax = max(t1, t2);
    float tNear = max(tmin.x, tmin.y);
    float tFar = min(tmax.x, tmax.y);
    if (tFar < 0.0 || tNear > tFar) return false;
    tHit = tNear < 0.0 ? tFar : tNear;
    return tHit >= 0.0 && tHit <= cone_len;
}

void main(){
    // Determine which agent and ray this pixel corresponds to.
    float idx = gl_FragCoord.x - 0.5;
    float agent_width = ray_steps + 1.0;
    int agent_idx = int(floor(idx / agent_width));
    float ray_idx = mod(idx, agent_width);

    // Fetch agent parameters from the textures.
    float u = (float(agent_idx) + 0.5) / agent_count;
    vec4 p0 = texture2D(agent0, vec2(u, 0.5));
    vec4 p1 = texture2D(agent1, vec2(u, 0.5));
    vec2 origin = p0.xy;
    float base_ang = p0.z;
    float fov_half = p0.w;
    float cone_len = p1.x;

    // Compute the ray direction for this pixel's sample.
    float t = ray_idx / ray_steps;
    float start_ang = base_ang + fov_half;
    float end_ang   = base_ang - fov_half;
    float ang = mix(start_ang, end_ang, t);
    vec2 dir = vec2(cos(ang), sin(ang));
    float best = cone_len;
    for(int i=0;i<512;i++){
        if(i>=collider_count) break;
        vec4 rect = get_rect(i);
        float h;
        if(intersect_rect(origin, dir, rect, cone_len, h)){
            if(h < best) best = h;
        }
    }
    gl_FragColor = vec4(best / cone_len, 0.0, 0.0, 1.0);
}
#endif

