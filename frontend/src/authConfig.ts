import { Configuration, LogLevel } from "@azure/msal-browser";

export const msalConfig: Configuration = {
  auth: {
    clientId: "7ce78d8d-cb7c-4def-8d7c-b2bf4c8544ae", // Application (client) ID from AAF-Factory-Dev
    authority: "https://login.microsoftonline.com/09c33f4e-3945-4c36-896d-35ec9632e7a1",
    redirectUri: window.location.origin, // auto-resolves to localhost in dev, your SWA URL in prod
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage", // safer default than localStorage for tokens
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
          default:
            return;
        }
      },
    },
  },
};

// Minimum scope needed for sign-in
export const loginRequest = {
  scopes: ["User.Read"],
};