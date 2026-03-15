/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      colors: {
        paper: '#FFFFFF',
        surface: '#FAFAFA',
        subtle: '#F4F4F5',
        ink: '#09090B',
        steel: '#71717A',
        accent: '#0070F3', // Crisp Vercel/Linear light mode blue
        danger: '#EF4444',
        warning: '#F59E0B',
        success: '#10B981',
        // Dark mode tokens
        night: '#0A0A0F',
        void: '#06060A',
        abyss: '#020204',
        frost: 'rgba(255,255,255,0.06)',
        wire: 'rgba(255,255,255,0.08)',
      },
      backgroundImage: {
        'hero-glow': 'radial-gradient(circle at 50% 0%, rgba(0, 112, 243, 0.06), transparent 50%)',
        'subtle-grid': 'linear-gradient(to right, rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.03) 1px, transparent 1px)'
      },
      boxShadow: {
        'glow': '0 0 40px -10px rgba(0, 112, 243, 0.15)',
        'glass': '0 4px 32px -4px rgba(0, 0, 0, 0.04)',
        'card': '0 1px 3px rgba(0,0,0,0.04), 0 10px 20px -5px rgba(0,0,0,0.02)',
      }
    },
  },
  plugins: [],
}
