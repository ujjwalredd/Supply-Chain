import createGlobe from "cobe";
import { useEffect, useRef } from "react";

export function CobeGlobe() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let phi = 0;

    const globe = createGlobe(canvasRef.current!, {
      devicePixelRatio: 2,
      width: 1200,
      height: 1200,
      phi: 0,
      theta: -0.1,
      dark: 0,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: 3,
      baseColor: [1, 1, 1], // white base
      markerColor: [0.1, 0.4, 1], // primary accent marker
      glowColor: [0.95, 0.95, 0.95],
      markers: [
        // Shenzhen
        { location: [22.5431, 114.0579], size: 0.1 },
        // Taipei
        { location: [25.033, 121.5654], size: 0.08 },
        // Shanghai
        { location: [31.2304, 121.4737], size: 0.12 },
        // Tokyo
        { location: [35.6762, 139.6503], size: 0.08 },
        // San Fran
        { location: [37.7749, -122.4194], size: 0.08 },
        // Austin
        { location: [30.2672, -97.7431], size: 0.06 },
        // Berlin
        { location: [52.52, 13.405], size: 0.08 }
      ],
      onRender: (state) => {
        // Called on every animation frame.
        // `state` will be an empty object, return updated params.
        state.phi = phi;
        phi += 0.005;
      },
    });

    return () => {
      globe.destroy();
    };
  }, []);

  return (
    <div style={{ width: "600px", height: "600px", margin: "0 auto", position: "relative" }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", contain: "layout paint size", opacity: 0.9, mixBlendMode: 'multiply' }}
      />
    </div>
  );
}
