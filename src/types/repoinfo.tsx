export interface RepoInfo {
    owner: string;
    repo: string;
    type: 'github' | 'local'; // Only GitHub repositories are supported
    token: string | null;
    localPath: string | null;
    repoUrl: string | null;
}

export default RepoInfo;