/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                "primary": "#135bec",
                "background-light": "#f6f6f8",
                "background-dark": "#0b0c15",
                "surface-dark": "#151a23",
                "glass-border": "rgba(255, 255, 255, 0.08)",
                "accent-cyan": "#00f0ff",
                "accent-pink": "#ff0099",
                "accent-green": "#0bda5e",
                "accent-red": "#ef4444",
            },
            fontFamily: {
                "display": ["Space Grotesk", "sans-serif"],
                "body": ["Noto Sans", "sans-serif"],
            },
            container: {
                center: true,
                padding: '2rem',
            },
            backgroundImage: {
                'gradient-dark': 'radial-gradient(circle at top right, #1e2636 0%, #101622 100%)',
            }
        },
    },
    plugins: [],
}
