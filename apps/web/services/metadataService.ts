import { apiClient } from './axios';
import {
  MetadataSnapshotDetailResponse,
  MetadataSnapshotResponse,
} from '../types/metadata';

export const metadataService = {
  /**
   * Fetch the latest metadata snapshot for a given data source
   */
  async getLatestSnapshot(sourceId: string): Promise<MetadataSnapshotDetailResponse> {
    const response = await apiClient.get<MetadataSnapshotDetailResponse>(
      `/metadata/sources/${sourceId}/snapshots/latest`
    );
    return response.data;
  },

  /**
   * List snapshot history for a given data source
   */
  async listSnapshots(sourceId: string): Promise<MetadataSnapshotResponse[]> {
    const response = await apiClient.get<MetadataSnapshotResponse[]>(
      `/metadata/sources/${sourceId}/snapshots`
    );
    return response.data;
  },

  /**
   * Fetch a specific metadata snapshot by ID
   */
  async getSnapshotById(snapshotId: string): Promise<MetadataSnapshotDetailResponse> {
    const response = await apiClient.get<MetadataSnapshotDetailResponse>(
      `/metadata/snapshots/${snapshotId}`
    );
    return response.data;
  },

  /**
   * Delete a snapshot
   */
  async deleteSnapshot(snapshotId: string): Promise<void> {
    await apiClient.delete(`/metadata/snapshots/${snapshotId}`);
  },
};

export default metadataService;
