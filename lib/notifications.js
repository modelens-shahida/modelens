// Notifications API Service
import { api } from "@/lib/api";

export const notificationsApi = {
  // Get notifications (paginated, unread_only option)
  list: async (unreadOnly = false, limit = 10, offset = 0) => {
    return await api.get(`/api/v1/notifications?unread_only=${unreadOnly}&limit=${limit}&offset=${offset}`);
  },

  // Mark a single notification as read
  markAsRead: async (id) => {
    return await api.put(`/api/v1/notifications/${id}/read`);
  },

  // Mark all notifications as read
  markAllAsRead: async () => {
    return await api.put("/api/v1/notifications/read-all");
  },

  // Delete a specific notification
  delete: async (id) => {
    return await api.delete(`/api/v1/notifications/${id}`);
  },

  // Get notification preferences
  getPreferences: async () => {
    return await api.get("/api/v1/notifications/preferences");
  },

  // Update notification preferences
  updatePreferences: async (preferences) => {
    return await api.put("/api/v1/notifications/preferences", preferences);
  },
};
