namespace SpeechRecognitionExample
{
    partial class MainForm
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.btnStartReco = new System.Windows.Forms.Button();
            this.txtRecoOutput = new System.Windows.Forms.TextBox();
            this.lblStatus = new System.Windows.Forms.Label();
            this.grpConfig = new System.Windows.Forms.GroupBox();
            this.txtModelId = new System.Windows.Forms.TextBox();
            this.lblModelId = new System.Windows.Forms.Label();
            this.txtApiUrl = new System.Windows.Forms.TextBox();
            this.lblApiUrl = new System.Windows.Forms.Label();
            this.btnTestFile = new System.Windows.Forms.Button();
            this.grpConfig.SuspendLayout();
            this.SuspendLayout();
            // 
            // btnStartReco
            // 
            this.btnStartReco.Font = new System.Drawing.Font("Microsoft Sans Serif", 10F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.btnStartReco.Location = new System.Drawing.Point(12, 140);
            this.btnStartReco.Name = "btnStartReco";
            this.btnStartReco.Size = new System.Drawing.Size(200, 40);
            this.btnStartReco.TabIndex = 0;
            this.btnStartReco.Text = "Start Recording";
            this.btnStartReco.UseVisualStyleBackColor = true;
            this.btnStartReco.Click += new System.EventHandler(this.btnStartReco_Click);
            // 
            // txtRecoOutput
            // 
            this.txtRecoOutput.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.txtRecoOutput.Font = new System.Drawing.Font("Consolas", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.txtRecoOutput.Location = new System.Drawing.Point(12, 186);
            this.txtRecoOutput.Multiline = true;
            this.txtRecoOutput.Name = "txtRecoOutput";
            this.txtRecoOutput.ReadOnly = true;
            this.txtRecoOutput.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
            this.txtRecoOutput.Size = new System.Drawing.Size(560, 250);
            this.txtRecoOutput.TabIndex = 1;
            // 
            // lblStatus
            // 
            this.lblStatus.AutoSize = true;
            this.lblStatus.Location = new System.Drawing.Point(12, 444);
            this.lblStatus.Name = "lblStatus";
            this.lblStatus.Size = new System.Drawing.Size(38, 13);
            this.lblStatus.TabIndex = 2;
            this.lblStatus.Text = "Ready";
            // 
            // grpConfig
            // 
            this.grpConfig.Controls.Add(this.txtModelId);
            this.grpConfig.Controls.Add(this.lblModelId);
            this.grpConfig.Controls.Add(this.txtApiUrl);
            this.grpConfig.Controls.Add(this.lblApiUrl);
            this.grpConfig.Location = new System.Drawing.Point(12, 12);
            this.grpConfig.Name = "grpConfig";
            this.grpConfig.Size = new System.Drawing.Size(560, 116);
            this.grpConfig.TabIndex = 3;
            this.grpConfig.TabStop = false;
            this.grpConfig.Text = "Configuration";
            // 
            // txtModelId
            // 
            this.txtModelId.Location = new System.Drawing.Point(80, 72);
            this.txtModelId.Name = "txtModelId";
            this.txtModelId.Size = new System.Drawing.Size(460, 20);
            this.txtModelId.TabIndex = 3;
            this.txtModelId.Text = "56b79c08-c58f-41cd-a7b6-f515ba04b5b6";
            // 
            // lblModelId
            // 
            this.lblModelId.AutoSize = true;
            this.lblModelId.Location = new System.Drawing.Point(20, 75);
            this.lblModelId.Name = "lblModelId";
            this.lblModelId.Size = new System.Drawing.Size(54, 13);
            this.lblModelId.TabIndex = 2;
            this.lblModelId.Text = "Model ID:";
            // 
            // txtApiUrl
            // 
            this.txtApiUrl.Location = new System.Drawing.Point(80, 30);
            this.txtApiUrl.Name = "txtApiUrl";
            this.txtApiUrl.Size = new System.Drawing.Size(460, 20);
            this.txtApiUrl.TabIndex = 1;
            this.txtApiUrl.Text = "https://www.soundsgood.health";
            // 
            // lblApiUrl
            // 
            this.lblApiUrl.AutoSize = true;
            this.lblApiUrl.Location = new System.Drawing.Point(20, 33);
            this.lblApiUrl.Name = "lblApiUrl";
            this.lblApiUrl.Size = new System.Drawing.Size(54, 13);
            this.lblApiUrl.TabIndex = 0;
            this.lblApiUrl.Text = "API URL:";
            // 
            // btnTestFile
            // 
            this.btnTestFile.Location = new System.Drawing.Point(230, 140);
            this.btnTestFile.Name = "btnTestFile";
            this.btnTestFile.Size = new System.Drawing.Size(200, 40);
            this.btnTestFile.TabIndex = 4;
            this.btnTestFile.Text = "Test with File";
            this.btnTestFile.UseVisualStyleBackColor = true;
            this.btnTestFile.Click += new System.EventHandler(this.btnTestFile_Click);
            // 
            // MainForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(584, 461);
            this.Controls.Add(this.btnTestFile);
            this.Controls.Add(this.grpConfig);
            this.Controls.Add(this.lblStatus);
            this.Controls.Add(this.txtRecoOutput);
            this.Controls.Add(this.btnStartReco);
            this.Name = "MainForm";
            this.Text = "SoundClassifiers Speech Recognition";
            this.grpConfig.ResumeLayout(false);
            this.grpConfig.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button btnStartReco;
        private System.Windows.Forms.TextBox txtRecoOutput;
        private System.Windows.Forms.Label lblStatus;
        private System.Windows.Forms.GroupBox grpConfig;
        private System.Windows.Forms.TextBox txtModelId;
        private System.Windows.Forms.Label lblModelId;
        private System.Windows.Forms.TextBox txtApiUrl;
        private System.Windows.Forms.Label lblApiUrl;
        private System.Windows.Forms.Button btnTestFile;
    }
}