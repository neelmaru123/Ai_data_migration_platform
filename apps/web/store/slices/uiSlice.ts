import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface UiState {
  sidebarOpen: boolean;
  themeMode: 'dark' | 'light' | 'system';
  notification: {
    type: 'success' | 'error' | 'info' | 'warning';
    message: string;
  } | null;
}

const initialState: UiState = {
  sidebarOpen: true,
  themeMode: 'dark',
  notification: null,
};

export const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen: (state, action: PayloadAction<boolean>) => {
      state.sidebarOpen = action.payload;
    },
    setThemeMode: (state, action: PayloadAction<'dark' | 'light' | 'system'>) => {
      state.themeMode = action.payload;
    },
    setNotification: (
      state,
      action: PayloadAction<{ type: 'success' | 'error' | 'info' | 'warning'; message: string } | null>
    ) => {
      state.notification = action.payload;
    },
    clearNotification: (state) => {
      state.notification = null;
    },
  },
});

export const {
  toggleSidebar,
  setSidebarOpen,
  setThemeMode,
  setNotification,
  clearNotification,
} = uiSlice.actions;

export default uiSlice.reducer;
