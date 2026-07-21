import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Text, Line } from '@react-three/drei';
import type { HexagramNode, AvatarPayload } from '../../lib/avatarProtocol';
import { binaryToSphereCoords } from '../../lib/ggwaveBridge';

function NodeMesh({ node, dominant }: { node: HexagramNode; dominant: boolean }) {
  const ref = useRef<any>(null);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const targetScale = dominant ? 1.35 : 1;
    const current = ref.current.scale.x ?? 1;
    const next = current + (targetScale - current) * Math.min(delta * 4, 1);
    ref.current.scale.setScalar(next);
  });

  const color = node.color || '#38bdf8';
  const position = useMemo<[number, number, number]>(() => [node.x, node.y, node.z], [node.x, node.y, node.z]);

  return (
    <group position={position}>
      <Sphere ref={ref} args={[node.radius, 12, 12]}>
        <meshStandardMaterial color={color} opacity={node.opacity} transparent depthWrite={false} />
      </Sphere>
      {dominant && (
        <Text position={[0, node.radius + 0.25, 0]} fontSize={0.22} color="#ffffff" anchorX="center" anchorY="middle">
          {node.unicode}
        </Text>
      )}
    </group>
  );
}

function ConnectionRing({ nodes }: { nodes: HexagramNode[] }) {
  const points = useMemo<number[]>(() => {
    if (nodes.length < 2) return [];
    const sorted = [...nodes].sort((a, b) => a.id - b.id).slice(0, 12);
    return sorted.flatMap((node, idx) => {
      const next = sorted[(idx + 1) % sorted.length];
      return [node.x, node.y, node.z, next.x, next.y, next.z];
    });
  }, [nodes]);

  if (points.length < 6) return null;

  return (
    <Line points={points} color="#38bdf8" opacity={0.18} transparent lineWidth={1} />
  );
}

function Scene({ payload }: { payload: AvatarPayload }) {
  const nodes = useMemo(() => payload.nodes.map((node) => ({
    ...node,
    x: node.x,
    y: node.y,
    z: node.z,
  })), [payload.nodes]);

  const dominantId = payload.dominant?.id ?? nodes[0]?.id;

  return (
    <>
      <ambientLight intensity={0.35} />
      <pointLight position={[4, 4, 4]} intensity={1.2} />
      <pointLight position={[-4, -2, -4]} intensity={0.6} color="#a78bfa" />

      <ConnectionRing nodes={nodes} />

      {nodes.map((node) => (
        <NodeMesh key={node.id} node={node} dominant={node.id === dominantId} />
      ))}

      <OrbitControls enableDamping dampingFactor={0.08} autoRotate autoRotateSpeed={0.6} />
    </>
  );
}

export function KingwenAvatar3D({ payload }: { payload: AvatarPayload }) {
  const ready = Boolean(payload && payload.nodes.length > 0);

  return (
    <div className="h-full w-full">
      <Canvas camera={{ position: [0, 0, 5.5], fov: 50 }}>
        {ready && <Scene payload={payload} />}
      </Canvas>
    </div>
  );
}
