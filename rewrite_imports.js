const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Find all files
const files = execSync('find frontend/src -type f -name "*.ts" -o -name "*.tsx"').toString().split('\n').filter(Boolean);

files.forEach(file => {
    let content = fs.readFileSync(file, 'utf8');
    let changed = false;
    
    // Replace @/... with relative path
    const fileDir = path.dirname(file);
    const srcDir = path.resolve('frontend/src');
    
    content = content.replace(/from\s+["']@\/(.*?)["']/g, (match, importPath) => {
        const targetPath = path.resolve(srcDir, importPath);
        let relPath = path.relative(fileDir, targetPath);
        if (!relPath.startsWith('.')) {
            relPath = './' + relPath;
        }
        changed = true;
        return `from "${relPath}"`;
    });
    
    if (changed) {
        fs.writeFileSync(file, content);
        console.log(`Updated ${file}`);
    }
});
