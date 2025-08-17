#ifdef GL_ES
precision highp float;
#endif

uniform vec2 origin;
uniform float base_ang;
uniform float fov_half;
uniform float cone_len;
uniform float ray_steps;

uniform sampler2D colliders;
uniform int collider_count;

vec4 get_rect(int idx){
    float u = (float(idx) + 0.5) / float(collider_count);
    return texture2D(colliders, vec2(u, 0.5));
}

bool intersect_rect(vec2 o, vec2 d, vec4 rect, out float tHit){
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
    float idx = gl_FragCoord.x - 0.5;
    float t = idx / ray_steps;
    float start_ang = base_ang + fov_half;
    float end_ang   = base_ang - fov_half;
    float ang = mix(start_ang, end_ang, t);
    vec2 dir = vec2(cos(ang), sin(ang));
    float best = cone_len;
    for(int i=0;i<512;i++){
        if(i>=collider_count) break;
        vec4 rect = get_rect(i);
        float h;
        if(intersect_rect(origin, dir, rect, h)){
            if(h < best) best = h;
        }
    }
    gl_FragColor = vec4(best / cone_len, 0.0, 0.0, 1.0);
}
