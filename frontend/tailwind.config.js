/** All colors flow from the Ocean theme tokens in src/index.css */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg1: "var(--bg1)",
        bg2: "var(--bg2)",
        accent: "var(--accent)",
        accent2: "var(--accent2)",
        ink: "var(--text)",
        muted: "var(--muted)",
        danger: "var(--danger)",
      },
      borderRadius: { glass: "var(--radius)" },
    },
  },
  plugins: [],
};
