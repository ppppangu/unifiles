#!/bin/bash

# Navigate to the user management server directory
cd /data/V2/user_management_server_old

# Create a backup of the original file
cp conversation_manager/postgresql_base.py conversation_manager/postgresql_base.py.bak

# Fix the indentation issue
# This sed command adds 4 spaces of indentation to line 243 if it follows a try statement on line 242
sed -i '242{N; s/try:\nconn/try:\n    conn/}' conversation_manager/postgresql_base.py

# Check if the fix was successful
if [ $? -eq 0 ]; then
    echo "Indentation fixed successfully!"
    echo "A backup of the original file was created at conversation_manager/postgresql_base.py.bak"
else
    echo "Failed to fix indentation. Please check the file manually."
fi

# Alternatively, you can manually edit the file using a text editor:
echo ""
echo "If the automatic fix didn't work, you can manually edit the file using:"
echo "nano conversation_manager/postgresql_base.py"
echo ""
echo "Find line 242-243 and make sure the code after 'try:' is properly indented, like this:"
echo "try:"
echo "    conn = self.connection_pool.getconn()"
echo ""
echo "Save the file after making the changes."
