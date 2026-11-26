"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

const ACCENT = 0xa34e35;
const SAGE = 0xb7bc92;
const OCHRE = 0xdba66f;

// Decorative torus knot with two orbiting spheres. The arch panel is plain CSS,
// so when WebGL is unavailable the colored panel is all that shows.
export function CareArt() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      // WebGL is not available. Leave the plain panel in place.
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.z = 6;

    const knotGeometry = new THREE.TorusKnotGeometry(0.95, 0.28, 160, 24);
    const knotMaterial = new THREE.MeshStandardMaterial({ color: ACCENT, roughness: 0.5 });
    const knot = new THREE.Mesh(knotGeometry, knotMaterial);

    const sphereGeometry = new THREE.SphereGeometry(0.26, 32, 32);
    const sageMaterial = new THREE.MeshStandardMaterial({ color: SAGE, roughness: 0.6 });
    const ochreMaterial = new THREE.MeshStandardMaterial({ color: OCHRE, roughness: 0.6 });
    const sageOrb = new THREE.Mesh(sphereGeometry, sageMaterial);
    const ochreOrb = new THREE.Mesh(sphereGeometry, ochreMaterial);
    scene.add(knot, sageOrb, ochreOrb);

    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const light = new THREE.DirectionalLight(0xffffff, 1.8);
    light.position.set(3, 4, 5);
    scene.add(light);

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (width === 0 || height === 0) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let time = 0;
    let frame = 0;

    const draw = () => {
      knot.rotation.x = time * 0.3;
      knot.rotation.y = time * 0.45;
      sageOrb.position.set(Math.cos(time) * 2.3, Math.sin(time * 0.7) * 0.6, Math.sin(time) * 2.3);
      ochreOrb.position.set(
        Math.cos(time + Math.PI) * 1.9,
        Math.cos(time * 0.5) * 0.9,
        Math.sin(time + Math.PI) * 1.9,
      );
      renderer.render(scene, camera);
    };

    const animate = () => {
      time += 0.01;
      draw();
      frame = requestAnimationFrame(animate);
    };

    if (reduceMotion) {
      draw();
    } else {
      animate();
    }

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      knotGeometry.dispose();
      sphereGeometry.dispose();
      knotMaterial.dispose();
      sageMaterial.dispose();
      ochreMaterial.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className="relative h-[250px] overflow-hidden rounded-t-[180px] rounded-b-[3px] bg-art sm:h-[310px]"
    >
      <div ref={containerRef} className="absolute inset-0" />
    </div>
  );
}
